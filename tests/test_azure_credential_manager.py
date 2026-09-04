import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

azure = types.ModuleType("azure")
azure_core = types.ModuleType("azure.core")
azure_exceptions = types.ModuleType("azure.core.exceptions")

class AzureError(Exception):
    pass

class ResourceNotFoundError(AzureError):
    pass

azure_exceptions.AzureError = AzureError
azure_exceptions.ResourceNotFoundError = ResourceNotFoundError
azure_core.exceptions = azure_exceptions

azure_identity = types.ModuleType("azure.identity")

class AzureCliCredential:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

class DefaultAzureCredential:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

azure_identity.AzureCliCredential = AzureCliCredential
azure_identity.DefaultAzureCredential = DefaultAzureCredential

azure_kv = types.ModuleType("azure.keyvault")
azure_kv_secrets = types.ModuleType("azure.keyvault.secrets")

class SecretClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

azure_kv_secrets.SecretClient = SecretClient
azure_kv.secrets = azure_kv_secrets
azure.keyvault = azure_kv
sys.modules.update({
    "azure": azure,
    "azure.core": azure_core,
    "azure.core.exceptions": azure_exceptions,
    "azure.identity": azure_identity,
    "azure.keyvault": azure_kv,
    "azure.keyvault.secrets": azure_kv_secrets,
})

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "agentic_rag_chatbot_enterprise_ready" / "backend" / "credentials" / "azure_credential_manager.py"
spec = importlib.util.spec_from_file_location("azure_credential_manager_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

AzureCredentialManager = module.AzureCredentialManager
SecretNotFoundError = module.SecretNotFoundError

class FakeSecretClient:
    def __init__(self, value="secret-value", error=None):
        self.value = value
        self.error = error
        self.calls = []
        self.closed = False

    def get_secret(self, name):
        self.calls.append(name)
        if self.error:
            raise self.error
        return SimpleNamespace(value=self.value)

    def close(self):
        self.closed = True

def manager(client=None, **kwargs):
    return AzureCredentialManager(
        key_vault_url="https://example.vault.azure.net",
        credential=Mock(),
        secret_client=client or FakeSecretClient(),
        **kwargs,
    )

def test_environment_secret_takes_precedence(monkeypatch):
    monkeypatch.setenv("MY_SECRET", "from-env")
    client = FakeSecretClient("from-key-vault")
    assert manager(client).get_secret("MY_SECRET") == "from-env"
    assert client.calls == []

def test_key_vault_secret_is_retrieved_and_cached():
    client = FakeSecretClient("vault-secret")
    m = manager(client, cache_ttl_seconds=300)
    assert m.get_secret("MY-SECRET") == "vault-secret"
    assert m.get_secret("MY-SECRET") == "vault-secret"
    assert client.calls == ["MY-SECRET"]

def test_optional_missing_secret_returns_none():
    client = FakeSecretClient(error=ResourceNotFoundError("missing"))
    assert manager(client).get_secret("MY-SECRET", required=False) is None

def test_required_missing_secret_raises_domain_error():
    client = FakeSecretClient(error=ResourceNotFoundError("missing"))
    with pytest.raises(SecretNotFoundError, match="MY-SECRET"):
        manager(client).get_secret("MY-SECRET")

def test_invalid_secret_name_is_rejected_before_network():
    client = FakeSecretClient()
    with pytest.raises(ValueError):
        manager(client).get_secret("bad/name")
    assert client.calls == []

def test_invalid_key_vault_url_is_rejected():
    with pytest.raises(ValueError):
        AzureCredentialManager(key_vault_url="http://example.vault.azure.net", credential=Mock())

def test_credential_selection_is_environment_aware():
    with patch.object(module, "AzureCliCredential") as cli:
        AzureCredentialManager.get_credential(environment="local", use_cli_for_local=True)
        cli.assert_called_once_with(additionally_allowed_tenants=["*"])
    with patch.object(module, "DefaultAzureCredential") as default:
        AzureCredentialManager.get_credential(environment="production")
        default.assert_called_once_with()

def test_close_releases_client_and_credential():
    credential = Mock()
    client = FakeSecretClient()
    AzureCredentialManager(
        key_vault_url="https://example.vault.azure.net",
        credential=credential,
        secret_client=client,
    ).close()
    assert client.closed is True
    credential.close.assert_called_once()
