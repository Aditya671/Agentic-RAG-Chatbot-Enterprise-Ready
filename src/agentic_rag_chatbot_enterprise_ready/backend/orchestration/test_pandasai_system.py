import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest


# Dependency-isolated regression suite for the PandasAI adapter.
pandasai_module = types.ModuleType("pandasai")
pandasai_openai_module = types.ModuleType("pandasai_openai")


class FakePandasDataFrame:
    created = []

    def __init__(self, dataframe, config=None):
        self.dataframe = dataframe
        self.config = config or {}
        self.created.append(self)

    def chat(self, question):
        return f"answer:{question}"


class FakeAzureOpenAI:
    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.created.append(kwargs)


pandasai_module.DataFrame = FakePandasDataFrame
pandasai_module.__version__ = "3.0.0"
pandasai_openai_module.AzureOpenAI = FakeAzureOpenAI

sys.modules["pandasai"] = pandasai_module
sys.modules["pandasai_openai"] = pandasai_openai_module

MODULE_PATH = Path("/mnt/data/pandasai_system_upgraded.py")
spec = importlib.util.spec_from_file_location(
    "pandasai_system_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

PandasAIConfig = module.PandasAIConfig
PandasAIDataFrameEngine = module.PandasAIDataFrameEngine
PandasAICSVEngineBuilder = module.PandasAICSVEngineBuilder
PandasAIConfigurationError = module.PandasAIConfigurationError
PandasAIQueryError = module.PandasAIQueryError


class Config:
    def __init__(self):
        self.llms = {
            "aoai": {
                "endpoint-east-us-2": "https://example.openai.azure.com/",
                "api-version-east-us-2": "2025-04-01-preview",
                "pandasai-deployment-name": "gpt-5.1-pandas",
            }
        }
        self.key_vault = {
            "azure_openai_api_key_name": "azure-key",
        }


class CredentialManager:
    def __init__(self, secrets=None):
        self.secrets = secrets or {}

    def get_secret(self, name):
        return self.secrets.get(name)


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch):
    FakePandasDataFrame.created.clear()
    FakeAzureOpenAI.created.clear()
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY_SECRET_NAME", raising=False)
    yield


def make_df():
    return pd.DataFrame(
        {
            "country": ["India", "US", "UK"],
            "revenue": [100, 200, 150],
        }
    )


def test_current_pandasai_3_api_is_preferred():
    df = make_df()
    engine = PandasAIDataFrameEngine(
        df,
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model=types.SimpleNamespace(value="gpt-5.1"),
    )

    assert isinstance(engine.engine, FakePandasDataFrame)


def test_azure_llm_configuration_uses_key_vault():
    PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "vault-secret"}),
        selected_model=types.SimpleNamespace(value="gpt-5.1"),
    )

    kwargs = FakeAzureOpenAI.created[-1]

    assert kwargs["api_token"] == "vault-secret"
    assert kwargs["azure_endpoint"] == "https://example.openai.azure.com/"
    assert kwargs["api_version"] == "2025-04-01-preview"
    assert kwargs["deployment_name"] == "gpt-5.1-pandas"


def test_environment_key_is_used_when_key_vault_secret_is_missing(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "environment-secret")

    PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager(),
        selected_model=types.SimpleNamespace(value="gpt-5.1"),
    )

    assert FakeAzureOpenAI.created[-1]["api_token"] == "environment-secret"


def test_missing_api_key_is_rejected():
    with pytest.raises(PandasAIConfigurationError, match="API key"):
        PandasAIDataFrameEngine(
            make_df(),
            config=Config(),
            credential_manager=CredentialManager(),
            selected_model=types.SimpleNamespace(value="gpt-5.1"),
        )


def test_missing_aoai_configuration_is_rejected():
    config = Config()
    config.llms = {}

    with pytest.raises(PandasAIConfigurationError, match="llms.aoai"):
        PandasAIDataFrameEngine(
            make_df(),
            config=config,
            credential_manager=CredentialManager({"azure-key": "secret"}),
            selected_model="gpt-5.1",
        )


def test_missing_endpoint_is_rejected():
    config = Config()
    config.llms["aoai"].pop("endpoint-east-us-2")

    with pytest.raises(PandasAIConfigurationError, match="endpoint"):
        PandasAIDataFrameEngine(
            make_df(),
            config=config,
            credential_manager=CredentialManager({"azure-key": "secret"}),
            selected_model="gpt-5.1",
        )


def test_missing_api_version_is_rejected():
    config = Config()
    config.llms["aoai"].pop("api-version-east-us-2")

    with pytest.raises(PandasAIConfigurationError, match="API version"):
        PandasAIDataFrameEngine(
            make_df(),
            config=config,
            credential_manager=CredentialManager({"azure-key": "secret"}),
            selected_model="gpt-5.1",
        )


def test_deployment_can_be_model_specific():
    config = Config()
    config.llms["aoai"]["pandasai-gpt-5.1"] = "custom-deployment"

    PandasAIDataFrameEngine(
        make_df(),
        config=config,
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    assert FakeAzureOpenAI.created[-1]["deployment_name"] == "custom-deployment"


def test_selected_model_enum_value_is_supported():
    model = types.SimpleNamespace(value="gpt-5.1")

    PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model=model,
    )

    assert FakeAzureOpenAI.created[-1]["deployment_name"] == "gpt-5.1-pandas"


def test_empty_dataframe_is_rejected():
    with pytest.raises(ValueError, match="at least one row"):
        PandasAIDataFrameEngine(
            pd.DataFrame({"x": []}),
            config=Config(),
            credential_manager=CredentialManager({"azure-key": "secret"}),
            selected_model="gpt-5.1",
        )


def test_non_dataframe_is_rejected():
    with pytest.raises(TypeError, match="pandas.DataFrame"):
        PandasAIDataFrameEngine(
            "not-a-dataframe",
            config=Config(),
            credential_manager=CredentialManager({"azure-key": "secret"}),
            selected_model="gpt-5.1",
        )


def test_query_preserves_legacy_query_contract():
    engine = PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    assert engine.query("What is total revenue?") == "answer:What is total revenue?"


def test_chat_is_alias_for_query():
    engine = PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    assert engine.chat("top country") == "answer:top country"


def test_empty_query_is_rejected():
    engine = PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    with pytest.raises(ValueError):
        engine.query(" ")


def test_query_error_is_normalized():
    class BrokenDataFrame(FakePandasDataFrame):
        def chat(self, question):
            raise RuntimeError("generated code failed")

    engine = PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
        dataframe_factory=BrokenDataFrame,
    )

    with pytest.raises(PandasAIQueryError, match="could not complete"):
        engine.query("bad query")


def test_csv_builder_loads_valid_csv():
    builder = PandasAICSVEngineBuilder(
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    engine = builder.build_from_blob(
        b"country,revenue\nIndia,100\nUS,200\n",
        {"description": "sales"},
    )

    assert list(engine.dataframe.columns) == ["country", "revenue"]


def test_csv_builder_parses_present_date_columns():
    builder = PandasAICSVEngineBuilder(
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    engine = builder.build_from_blob(
        b"createddate,activitydate,name\n2026-01-01,2026-01-02,Alice\n",
    )

    assert str(engine.dataframe["createddate"].dtype).startswith("datetime64")
    assert str(engine.dataframe["activitydate"].dtype).startswith("datetime64")


def test_csv_without_date_columns_is_supported():
    builder = PandasAICSVEngineBuilder(
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    engine = builder.build_from_blob(b"name,value\nAlice,10\n")

    assert list(engine.dataframe.columns) == ["name", "value"]


def test_empty_csv_is_rejected():
    builder = PandasAICSVEngineBuilder(
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    with pytest.raises(ValueError, match="must not be empty"):
        builder.build_from_blob(b"")


def test_empty_csv_data_rows_are_rejected():
    builder = PandasAICSVEngineBuilder(
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    with pytest.raises(ValueError, match="no data rows"):
        builder.build_from_blob(b"name,value\n")


def test_non_bytes_csv_input_is_rejected():
    builder = PandasAICSVEngineBuilder(
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    with pytest.raises(TypeError):
        builder.build_from_blob("name,value\nAlice,10\n")


def test_pandasai_config_defaults_are_safe():
    config = PandasAIConfig()

    assert config.verbose is False
    assert config.enforce_privacy is True
    assert config.max_retries == 3
    assert config.temperature == 0.0


def test_pandasai_config_validates_retries():
    with pytest.raises(ValueError):
        PandasAIConfig(max_retries=-1)


def test_pandasai_config_validates_temperature():
    with pytest.raises(ValueError):
        PandasAIConfig(temperature=3)


def test_privacy_is_enabled_by_default():
    PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    assert FakePandasDataFrame.created[-1].config["enforce_privacy"] is True


def test_verbose_is_disabled_by_default():
    PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    assert FakePandasDataFrame.created[-1].config["verbose"] is False


def test_max_retries_are_forwarded():
    PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
        pandasai_config=PandasAIConfig(max_retries=5),
    )

    assert FakePandasDataFrame.created[-1].config["max_retries"] == 5


def test_secret_value_is_not_logged(caplog):
    PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "super-secret"}),
        selected_model="gpt-5.1",
    )

    assert "super-secret" not in caplog.text


def test_api_token_is_not_written_to_environment():
    PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
    )

    assert "AZURE_OPENAI_API_KEY" not in os.environ


def test_type_error_fallback_supports_api_key_signature():
    class ApiKeyOnlyLLM:
        def __init__(self, **kwargs):
            if "api_token" in kwargs:
                raise TypeError("unexpected keyword")
            self.kwargs = kwargs

    llm = module._build_pandasai_llm(
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
        llm_factory=ApiKeyOnlyLLM,
    )

    assert llm.kwargs["api_key"] == "secret"


def test_source_no_longer_imports_legacy_pandas_query_engine():
    source = MODULE_PATH.read_text()

    assert "PandasQueryEngine" not in source
    assert "pandasai" in source
    assert "PandasAIDataFrameEngine" in source


def test_source_uses_current_pandasai_dataframe_api():
    source = MODULE_PATH.read_text()

    assert "pai.DataFrame" in source
    assert "SmartDataframe" in source  # compatibility fallback only


def test_query_result_scalar_is_normalized():
    class ScalarDataFrame(FakePandasDataFrame):
        def chat(self, question):
            return 42

    engine = PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
        dataframe_factory=ScalarDataFrame,
    )

    assert engine.query("count") == "42"


def test_query_result_none_is_normalized():
    class NoneDataFrame(FakePandasDataFrame):
        def chat(self, question):
            return None

    engine = PandasAIDataFrameEngine(
        make_df(),
        config=Config(),
        credential_manager=CredentialManager({"azure-key": "secret"}),
        selected_model="gpt-5.1",
        dataframe_factory=NoneDataFrame,
    )

    assert engine.query("nothing") == ""


def test_api_key_secret_name_can_be_overridden():
    config = Config()
    config.llms["aoai"]["api-key-secret-name"] = "custom-key"

    PandasAIDataFrameEngine(
        make_df(),
        config=config,
        credential_manager=CredentialManager({"custom-key": "custom-secret"}),
        selected_model="gpt-5.1",
    )

    assert FakeAzureOpenAI.created[-1]["api_token"] == "custom-secret"
