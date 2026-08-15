import copy
import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


# Dependency-isolated regression harness. No Azure/OpenAI network calls are
# made by these tests.
azure_identity = types.ModuleType("azure.identity")


class FakeCredential:
    pass


class FakeTokenProvider:
    pass


def fake_default_credential():
    return FakeCredential()


def fake_bearer_token_provider(credential, scope):
    return FakeTokenProvider()


azure_identity.DefaultAzureCredential = fake_default_credential
azure_identity.get_bearer_token_provider = fake_bearer_token_provider

llama_index = types.ModuleType("llama_index")
core = types.ModuleType("llama_index.core")
llms = types.ModuleType("llama_index.core.llms")
llms_llm = types.ModuleType("llama_index.core.llms.llm")
llms_azure = types.ModuleType("llama_index.llms.azure_openai")
llms_openai = types.ModuleType("llama_index.llms.openai")
embeddings_azure = types.ModuleType("llama_index.embeddings.azure_openai")
embeddings_openai = types.ModuleType("llama_index.embeddings.openai")

backend = types.ModuleType("backend")
ai_models = types.ModuleType("backend.ai_models")
config_module = types.ModuleType("backend.config")
credential_module = types.ModuleType("backend.azure_credential_manager")


class Model:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value == getattr(other, "value", other)

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return f"Model({self.value!r})"


class AIModelTypes:
    GPT51 = Model("gpt-5.1")
    GPT41_MINI = Model("gpt-4.1-mini")
    O4_MINI = Model("o4-mini")
    O4_MINI_HIGH = Model("o4-mini-high")

    _values = {
        "gpt-5.1": GPT51,
        "gpt-4.1-mini": GPT41_MINI,
        "o4-mini": O4_MINI,
        "o4-mini-high": O4_MINI_HIGH,
    }

    def __new__(cls, value):
        if isinstance(value, Model):
            return value
        return cls._values[value]


class FakeIndexConfig:
    def __init__(
        self,
        *,
        llms=None,
        embed=None,
        key_vault=None,
    ):
        self.llms = llms if llms is not None else {}
        self.embed = embed if embed is not None else {}
        self.key_vault = key_vault


class FakeConfig:
    def __init__(self):
        self.indexes = {
            "test": FakeIndexConfig(
                llms={
                    "aoai": {
                        "endpoint-east-us-2": "https://example.openai.azure.com",
                        "api-version-east-us-2": "2025-04-01-preview",
                    }
                },
                embed={"model": "text-embedding-3-small"},
                key_vault={"url": "https://vault.example"},
            )
        }


class FakeCredentialManager:
    secrets = {}

    def __init__(self, key_vault_url):
        self.key_vault_url = key_vault_url

    def get_secret(self, name):
        return self.secrets.get(name)


class CapturingLLM:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        CapturingLLM.instances.append(self.kwargs)


class CapturingEmbedding:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        CapturingEmbedding.instances.append(self.kwargs)


class AzureOpenAI(CapturingLLM):
    pass


class OpenAI(CapturingLLM):
    pass


class AzureOpenAIEmbedding(CapturingEmbedding):
    pass


class OpenAIEmbedding(CapturingEmbedding):
    pass


llms_llm.LLM = object
llms_azure.AzureOpenAI = AzureOpenAI
llms_openai.OpenAI = OpenAI
embeddings_azure.AzureOpenAIEmbedding = AzureOpenAIEmbedding
embeddings_openai.OpenAIEmbedding = OpenAIEmbedding

ai_models.AIModelTypes = AIModelTypes
config_module.IndexConfig = FakeIndexConfig
config_module.config = FakeConfig()
credential_module.AzureCredentialManager = FakeCredentialManager

sys.modules.update(
    {
        "azure": types.ModuleType("azure"),
        "azure.identity": azure_identity,
        "llama_index": llama_index,
        "llama_index.core": core,
        "llama_index.core.llms": llms,
        "llama_index.core.llms.llm": llms_llm,
        "llama_index.llms.azure_openai": llms_azure,
        "llama_index.llms.openai": llms_openai,
        "llama_index.embeddings.azure_openai": embeddings_azure,
        "llama_index.embeddings.openai": embeddings_openai,
        "backend": backend,
        "backend.ai_models": ai_models,
        "backend.config": config_module,
        "backend.azure_credential_manager": credential_module,
    }
)

MODULE_PATH = Path("/mnt/data/llm_loader_upgraded.py")
spec = importlib.util.spec_from_file_location("llm_loader_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

load_llm = module.load_llm
load_embed = module.load_embed
LLMConfigurationError = module.LLMConfigurationError


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    CapturingLLM.instances.clear()
    CapturingEmbedding.instances.clear()
    FakeCredentialManager.secrets.clear()

    # Every regression test gets an isolated configuration snapshot so a
    # negative test cannot contaminate later tests.
    module.config = FakeConfig()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_SECRET_NAME", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY_SECRET_NAME", raising=False)
    yield


def test_missing_index_configuration_is_explicit():
    with pytest.raises(LLMConfigurationError, match="not found"):
        load_llm(AIModelTypes.GPT51, "missing")


def test_empty_index_name_is_rejected():
    with pytest.raises(LLMConfigurationError, match="index_name"):
        load_llm(AIModelTypes.GPT51, "")


def test_invalid_timeout_is_rejected():
    with pytest.raises(LLMConfigurationError):
        load_llm(AIModelTypes.GPT51, "test", timeout=0)


def test_invalid_temperature_is_rejected():
    with pytest.raises(LLMConfigurationError):
        load_llm(AIModelTypes.GPT51, "test", temperature=3)


def test_invalid_additional_kwargs_type_is_rejected():
    with pytest.raises(TypeError):
        load_llm(AIModelTypes.GPT51, "test", additional_kwargs=[])


def test_mutable_kwargs_are_not_shared_between_calls():
    original = {"reasoning_effort": "low"}

    load_llm(AIModelTypes.GPT51, "test", additional_kwargs=original)
    load_llm(AIModelTypes.GPT51, "test", additional_kwargs=original)

    assert CapturingLLM.instances[0]["additional_kwargs"] is not original
    assert CapturingLLM.instances[1]["additional_kwargs"] is not original
    assert CapturingLLM.instances[0]["additional_kwargs"] == original


def test_azure_managed_identity_is_default(monkeypatch):
    load_llm(AIModelTypes.GPT51, "test", use_azure=True)

    kwargs = CapturingLLM.instances[-1]

    assert kwargs["azure_endpoint"] == "https://example.openai.azure.com"
    assert kwargs["api_version"] == "2025-04-01-preview"
    assert kwargs["engine"] == "gpt-5.1"
    assert kwargs["use_azure_ad"] is True
    assert isinstance(kwargs["azure_ad_token_provider"], FakeTokenProvider)


def test_azure_api_key_mode_does_not_create_managed_identity_provider(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-secret")

    load_llm(
        AIModelTypes.GPT51,
        "test",
        use_azure=True,
        azure_openai_use_azure_ad=False,
    )

    kwargs = CapturingLLM.instances[-1]

    assert kwargs["api_key"] == "azure-secret"
    assert "azure_ad_token_provider" not in kwargs
    assert "use_azure_ad" not in kwargs


def test_azure_api_key_can_come_from_key_vault(monkeypatch):
    FakeCredentialManager.secrets["aoai-key"] = "vault-secret"
    module.config.indexes["test"].llms["aoai"]["api-key-secret-name"] = "aoai-key"

    load_llm(
        AIModelTypes.GPT51,
        "test",
        use_azure=True,
        azure_openai_use_azure_ad=False,
    )

    assert CapturingLLM.instances[-1]["api_key"] == "vault-secret"


def test_azure_api_key_is_required_in_key_mode(monkeypatch):
    with pytest.raises(LLMConfigurationError, match="API key"):
        load_llm(
            AIModelTypes.GPT51,
            "test",
            use_azure=True,
            azure_openai_use_azure_ad=False,
        )


def test_openai_mode_uses_environment_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")

    load_llm(AIModelTypes.GPT51, "test", use_azure=False)

    kwargs = CapturingLLM.instances[-1]

    assert kwargs["api_key"] == "openai-secret"
    assert kwargs["model"] == "gpt-5.1"


def test_openai_mode_uses_key_vault_before_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    FakeCredentialManager.secrets["openai-key"] = "vault-secret"
    module.config.indexes["test"].key_vault["openai_api_key_name"] = "openai-key"

    load_llm(AIModelTypes.GPT51, "test", use_azure=False)

    assert CapturingLLM.instances[-1]["api_key"] == "vault-secret"


def test_openai_mode_requires_api_key(monkeypatch):
    with pytest.raises(LLMConfigurationError, match="OpenAI API key"):
        load_llm(AIModelTypes.GPT51, "test", use_azure=False)


def test_o4_mini_high_maps_to_o4_mini_with_high_reasoning():
    os.environ["OPENAI_API_KEY"] = "secret"

    load_llm(AIModelTypes.O4_MINI_HIGH, "test", use_azure=False)

    kwargs = CapturingLLM.instances[-1]

    assert kwargs["model"] == "o4-mini"
    assert kwargs["additional_kwargs"]["reasoning_effort"] == "high"


def test_explicit_reasoning_effort_is_not_overwritten_for_o4_high():
    os.environ["OPENAI_API_KEY"] = "secret"

    load_llm(
        AIModelTypes.O4_MINI_HIGH,
        "test",
        use_azure=False,
        additional_kwargs={"reasoning_effort": "low"},
    )

    assert CapturingLLM.instances[-1]["additional_kwargs"]["reasoning_effort"] == "low"


def test_azure_deployment_can_be_overridden():
    module.config.indexes["test"].llms["aoai"]["gpt-5.1"] = "prod-gpt51-deployment"

    load_llm(AIModelTypes.GPT51, "test")

    assert CapturingLLM.instances[-1]["engine"] == "prod-gpt51-deployment"


def test_missing_azure_endpoint_is_rejected():
    module.config.indexes["test"].llms["aoai"].pop("endpoint-east-us-2")

    with pytest.raises(LLMConfigurationError, match="endpoint"):
        load_llm(AIModelTypes.GPT51, "test")


def test_missing_azure_api_version_is_rejected():
    module.config.indexes["test"].llms["aoai"].pop("api-version-east-us-2")

    with pytest.raises(LLMConfigurationError, match="API version"):
        load_llm(AIModelTypes.GPT51, "test")


def test_missing_azure_configuration_is_rejected():
    module.config.indexes["test"].llms = {}

    with pytest.raises(LLMConfigurationError, match="aoai"):
        load_llm(AIModelTypes.GPT51, "test")


def test_embedding_azure_managed_identity():
    load_embed("test")

    kwargs = CapturingEmbedding.instances[-1]

    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["deployment_name"] == "text-embedding-3-small"
    assert kwargs["use_azure_ad"] is True
    assert isinstance(kwargs["azure_ad_token_provider"], FakeTokenProvider)


def test_embedding_azure_api_key_mode(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-secret")

    load_embed("test", azure_openai_use_azure_ad=False)

    kwargs = CapturingEmbedding.instances[-1]

    assert kwargs["api_key"] == "azure-secret"
    assert "azure_ad_token_provider" not in kwargs


def test_embedding_openai_mode(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")

    load_embed("test", use_azure=False)

    kwargs = CapturingEmbedding.instances[-1]

    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["api_key"] == "openai-secret"


def test_embedding_openai_mode_requires_api_key():
    with pytest.raises(LLMConfigurationError, match="OpenAI API key"):
        load_embed("test", use_azure=False)


def test_missing_embedding_model_is_rejected():
    module.config.indexes["test"].embed = {}

    with pytest.raises(LLMConfigurationError, match="Embedding model"):
        load_embed("test")


def test_embedding_deployment_can_be_overridden():
    module.config.indexes["test"].llms["aoai"]["embedding-deployment-name"] = "embed-prod"

    load_embed("test")

    assert CapturingEmbedding.instances[-1]["deployment_name"] == "embed-prod"


def test_timeout_is_forwarded_to_llm():
    load_llm(AIModelTypes.GPT51, "test", timeout=25)

    assert CapturingLLM.instances[-1]["request_timeout"] == 25.0


def test_timeout_is_forwarded_to_embedding():
    load_embed("test", timeout=17)

    assert CapturingEmbedding.instances[-1]["request_timeout"] == 17.0


def test_no_secret_values_are_logged(caplog, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "super-secret-value")

    load_llm(
        AIModelTypes.GPT51,
        "test",
        use_azure=True,
        azure_openai_use_azure_ad=False,
    )

    assert "super-secret-value" not in caplog.text


def test_key_vault_is_not_required_for_environment_only_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    module.config.indexes["test"].key_vault = None

    load_llm(AIModelTypes.GPT51, "test", use_azure=False)

    assert CapturingLLM.instances[-1]["api_key"] == "environment-secret"


def test_key_vault_is_not_required_for_environment_only_azure_key(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "environment-secret")
    module.config.indexes["test"].key_vault = None

    load_llm(
        AIModelTypes.GPT51,
        "test",
        use_azure=True,
        azure_openai_use_azure_ad=False,
    )

    assert CapturingLLM.instances[-1]["api_key"] == "environment-secret"


def test_index_config_is_validated_before_key_vault_access():
    module.config.indexes["test"] = FakeIndexConfig(
        llms={
            "aoai": {
                "endpoint-east-us-2": "https://example.openai.azure.com",
                "api-version-east-us-2": "2025-04-01-preview",
            }
        },
        embed={"model": "text-embedding-3-small"},
        key_vault=None,
    )

    # Azure AD mode does not need a Key Vault URL.
    load_llm(AIModelTypes.GPT51, "test", use_azure=True)

    assert CapturingLLM.instances[-1]["use_azure_ad"] is True


def test_azure_key_secret_name_can_be_configured_in_aoai_block():
    FakeCredentialManager.secrets["named-secret"] = "vault-secret"
    module.config.indexes["test"].llms["aoai"]["api-key-secret-name"] = "named-secret"

    load_llm(
        AIModelTypes.GPT51,
        "test",
        use_azure=True,
        azure_openai_use_azure_ad=False,
    )

    assert CapturingLLM.instances[-1]["api_key"] == "vault-secret"


def test_model_is_normalized_from_string_value():
    os.environ["OPENAI_API_KEY"] = "secret"

    load_llm("gpt-5.1", "test", use_azure=False)

    assert CapturingLLM.instances[-1]["model"] == "gpt-5.1"
