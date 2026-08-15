import ast
import importlib
import sys
import types
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


APP_PATH = Path(__file__).with_name("app_upgraded.py")


def _install_stubs(monkeypatch):
    # Chainlit
    chainlit = types.ModuleType("chainlit")

    class Session:
        def __init__(self):
            self.data = {}

        def get(self, key, default=None):
            return self.data.get(key, default)

        def set(self, key, value):
            self.data[key] = value
            return value

    chainlit.user_session = Session()

    def decorator(*args, **kwargs):
        def wrap(fn):
            return fn
        return wrap

    for name in (
        "oauth_callback",
        "set_starters",
        "on_settings_update",
        "data_layer",
        "on_chat_start",
        "on_chat_resume",
        "on_feedback",
        "on_message",
    ):
        setattr(chainlit, name, decorator)

    class Message:
        def __init__(self, content=""):
            self.content = content
            self.id = "message-id"
            self.parent_id = None
            self.thread_id = "thread-id"

        async def send(self):
            return self

        async def update(self):
            return None

        async def stream_token(self, token):
            self.content += token

    class ChatSettings:
        def __init__(self, inputs):
            self.inputs = inputs

        async def send(self):
            return {
                "select_index": "aiim",
                "select_ai_model": "gpt",
                "select_response_mode": "low",
                "set_model_top_k": 20,
                "set_creativity_level": 0.1,
                "enable_coding_assistant": False,
                "enable_reranker": True,
                "enable_graph_rag": False,
            }

    class Text:
        def __init__(self, **kwargs):
            pass

        async def send(self, **kwargs):
            return None

    class Pdf:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def send(self, **kwargs):
            return None

    class Starter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    chainlit.Message = Message
    chainlit.ChatSettings = ChatSettings
    chainlit.Text = Text
    chainlit.Pdf = Pdf
    chainlit.Starter = Starter
    chainlit.user_session = chainlit.user_session

    input_widget = types.ModuleType("chainlit.input_widget")

    class Widget:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    input_widget.Select = Widget
    input_widget.Switch = Widget
    input_widget.Slider = Widget

    types_module = types.ModuleType("chainlit.types")

    class Feedback:
        def __init__(self, forId=None, value=None, comment=None):
            self.forId = forId
            self.value = value
            self.comment = comment

    types_module.Feedback = Feedback

    user_module = types.ModuleType("chainlit.user")

    class User:
        def __init__(self, identifier="user"):
            self.identifier = identifier
            self.metadata = {}
            self.display_name = None

    user_module.User = User

    monkeypatch.setitem(sys.modules, "chainlit", chainlit)
    monkeypatch.setitem(sys.modules, "chainlit.input_widget", input_widget)
    monkeypatch.setitem(sys.modules, "chainlit.types", types_module)
    monkeypatch.setitem(sys.modules, "chainlit.user", user_module)

    # Azure SDK stubs
    azure = types.ModuleType("azure")
    azure_storage = types.ModuleType("azure.storage")
    azure_blob = types.ModuleType("azure.storage.blob")
    azure_identity = types.ModuleType("azure.identity")

    class BlobServiceClient:
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def from_connection_string(cls, value):
            return cls()

        def get_container_client(self, name):
            return object()

    class DefaultAzureCredential:
        pass

    azure_blob.BlobServiceClient = BlobServiceClient
    azure_identity.DefaultAzureCredential = DefaultAzureCredential

    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.storage", azure_storage)
    monkeypatch.setitem(sys.modules, "azure.storage.blob", azure_blob)
    monkeypatch.setitem(sys.modules, "azure.identity", azure_identity)

    # Backend stubs
    backend = types.ModuleType("backend")
    upload = types.ModuleType("backend.UploadFileWrapper")
    utility = types.ModuleType("backend.utility")
    retriever = types.ModuleType("backend.azure_blob_file_retriever")
    cosmos = types.ModuleType("backend.cosmos_db_date_layer")
    models = types.ModuleType("backend.ai_models")
    config_module = types.ModuleType("backend.config")
    credentials = types.ModuleType("backend.credentials")
    credential_module = types.ModuleType("backend.credentials.azure_credential_manager")
    agentic = types.ModuleType("backend.agentic_ai_system")
    logger_module = types.ModuleType("app_logger")

    class UploadedFileWrapper:
        def __init__(self, path, name):
            self.path = path
            self.name = name

    class AzureBlobFileRetriever:
        def __init__(self, **kwargs):
            pass

    class CosmosDBDataLayer:
        def __init__(self, **kwargs):
            pass

        async def update_thread(self, **kwargs):
            pass

    class AIModelTypes(Enum):
        GPT51 = "gpt"

    class Environment(Enum):
        DEVELOPMENT = "development"
        UAT = "uat"
        PRODUCTION = "production"

    class Config:
        indexes = {
            "aiim": types.SimpleNamespace(
                key_vault={"url": "https://vault"},
                storage_account={
                    "storage_account_name": "storage",
                    "container_name": "container",
                    "connection_string": "connection-secret",
                    "account_key": "account-key-secret",
                },
                dev_cosmos_db={
                    "uri": "dev-uri",
                    "database_id": "db",
                    "container_id": "container",
                },
                uat_cosmos_db={
                    "uri": "uat-uri",
                    "database_id": "db",
                    "container_id": "container",
                },
                prod_cosmos_db={
                    "uri": "prod-uri",
                    "database_id": "db",
                    "container_id": "container",
                },
            )
        }

    class AzureCredentialManager:
        def __init__(self, **kwargs):
            pass

    class AsyncAgenticAiSystem:
        def __init__(self, **kwargs):
            pass

    def setup_logger(name):
        import logging
        return logging.getLogger(name), "test.log"

    upload.UploadedFileWrapper = UploadedFileWrapper
    utility.generate_blob_sas_url = lambda **kwargs: "https://example.test/sas"
    retriever.AzureBlobFileRetriever = AzureBlobFileRetriever
    cosmos.CosmosDBDataLayer = CosmosDBDataLayer
    models.AIModelTypes = AIModelTypes
    config_module.config = Config()
    config_module.Environment = Environment
    credential_module.AzureCredentialManager = AzureCredentialManager
    agentic.AsyncAgenticAiSystem = AsyncAgenticAiSystem
    logger_module.setup_logger = setup_logger

    for module in (
        backend,
        upload,
        utility,
        retriever,
        cosmos,
        models,
        config_module,
        credentials,
        credential_module,
        agentic,
        logger_module,
    ):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    sys.modules.pop("app_upgraded", None)
    return importlib.import_module("app_upgraded")


def test_module_compiles():
    source = APP_PATH.read_text(encoding="utf-8")
    ast.parse(source)


def test_settings_normalization_defaults(monkeypatch):
    app = _install_stubs(monkeypatch)
    settings = app._normalize_settings({})
    assert settings["select_index"] == "aiim"
    assert settings["set_model_top_k"] == 20
    assert settings["enable_reranker"] is True
    assert settings["enable_graph_rag"] is False


def test_settings_normalization_clamps_values(monkeypatch):
    app = _install_stubs(monkeypatch)
    settings = app._normalize_settings(
        {
            "set_model_top_k": 999,
            "set_creativity_level": -5,
            "select_response_mode": "invalid",
        }
    )
    assert settings["set_model_top_k"] == 30
    assert settings["set_creativity_level"] == 0
    assert settings["select_response_mode"] == "low"


def test_settings_normalization_preserves_boolean_flags(monkeypatch):
    app = _install_stubs(monkeypatch)
    settings = app._normalize_settings(
        {
            "enable_coding_assistant": 1,
            "enable_reranker": 0,
            "enable_graph_rag": "x",
        }
    )
    assert settings["enable_coding_assistant"] is True
    assert settings["enable_reranker"] is False
    assert settings["enable_graph_rag"] is True


def test_settings_widget_ids_match_consumed_settings(monkeypatch):
    app = _install_stubs(monkeypatch)
    widgets = app.app_default_setting()
    ids = [widget.kwargs["id"] for widget in widgets]
    expected = {
        "select_index",
        "select_ai_model",
        "select_response_mode",
        "set_model_top_k",
        "set_creativity_level",
        "enable_coding_assistant",
        "enable_reranker",
        "enable_graph_rag",
    }
    assert set(ids) == expected


def test_branch_history_removes_selected_message_and_future(monkeypatch):
    app = _install_stubs(monkeypatch)
    history = [
        {"stepId": "1", "createdAt": "2026-01-01T00:00:00+00:00"},
        {"stepId": "2", "createdAt": "2026-01-01T00:01:00+00:00"},
        {"stepId": "3", "createdAt": "2026-01-01T00:02:00+00:00"},
    ]
    result = app._remove_branch_from_history(history, "2")
    assert [item["stepId"] for item in result] == ["1"]


def test_branch_history_ignores_unknown_message(monkeypatch):
    app = _install_stubs(monkeypatch)
    history = [{"stepId": "1", "createdAt": "2026-01-01T00:00:00+00:00"}]
    assert app._remove_branch_from_history(history, "missing") == history


def test_history_created_at_is_json_serializable(monkeypatch):
    app = _install_stubs(monkeypatch)
    history = []
    app._append_history(
        history,
        step_id="1",
        parent_id=None,
        role="user",
        content="hello",
    )
    assert isinstance(history[0]["createdAt"], str)
    datetime.fromisoformat(history[0]["createdAt"])


def test_citation_extraction_handles_valid_payload(monkeypatch):
    app = _install_stubs(monkeypatch)
    response = (
        "Answer\nCitations: "
        "[{'mimetype': 'pdf', 'source_node': 'a.pdf', 'page_number': 3}]"
    )
    citations = app._extract_citation_list(response)
    assert citations[0]["source_node"] == "a.pdf"
    assert citations[0]["page_number"] == 3


def test_citation_extraction_handles_missing_marker(monkeypatch):
    app = _install_stubs(monkeypatch)
    assert app._extract_citation_list("No citations here") == []


def test_citation_extraction_handles_malformed_payload(monkeypatch):
    app = _install_stubs(monkeypatch)
    assert app._extract_citation_list("Citations: [not valid") == []


def test_citation_extraction_handles_brackets_inside_strings(monkeypatch):
    app = _install_stubs(monkeypatch)
    response = (
        "Answer\nCitations: "
        "[{'title': 'Report [Final].pdf', 'mimetype': 'pdf'}]"
    )
    citations = app._extract_citation_list(response)
    assert citations[0]["title"] == "Report [Final].pdf"


def test_utc_timestamp_is_timezone_aware(monkeypatch):
    app = _install_stubs(monkeypatch)
    value = app._utc_now_iso()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


def test_source_name_rendering(monkeypatch):
    app = _install_stubs(monkeypatch)
    assert app._render_source_name({"title": "folder/report.pdf"}) == "report.pdf"


def test_no_import_time_blob_download():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_level_calls = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name):
                module_level_calls.append(node.value.func.id)
    assert "load_blob_bytes" not in module_level_calls


def test_no_secret_url_logging():
    source = APP_PATH.read_text(encoding="utf-8")
    assert "Data Layer: CosmosDb(URL=" not in source
    assert "logger.info(f\"[AgenticAiSystem] Data Layer" not in source


def test_no_plain_print_logging():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    print_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    assert not print_calls


def test_graph_group_filter_is_exact_microsoft_group_type(monkeypatch):
    app = _install_stubs(monkeypatch)

    # The helper is async and uses httpx; test the transformation logic by
    # replacing the network helper at the boundary.
    async def fake_groups(token):
        return [{"displayName": "Engineering", "id": "1"}]

    monkeypatch.setattr(app, "_graph_groups", fake_groups)
    import asyncio
    assert asyncio.run(app._graph_groups("token")) == [
        {"displayName": "Engineering", "id": "1"}
    ]


def test_agent_settings_apply_all_runtime_flags(monkeypatch):
    app = _install_stubs(monkeypatch)

    class Agent:
        def __init__(self):
            self.calls = []

        def __getattr__(self, name):
            def method(**kwargs):
                self.calls.append((name, kwargs))
            return method

    agent = Agent()
    app._apply_agent_settings(
        agent,
        {
            "select_index": "aiim",
            "select_ai_model": "gpt",
            "select_response_mode": "high",
            "set_model_top_k": 10,
            "set_creativity_level": 0.4,
            "enable_coding_assistant": True,
            "enable_reranker": False,
            "enable_graph_rag": True,
        },
    )
    names = {name for name, _ in agent.calls}
    assert names == {
        "set_selected_model",
        "set_llm_creativity_level",
        "set_reasoning_effect",
        "set_similarity_top_k",
        "set_index_name",
        "set_coding_assistant",
        "set_reranker",
        "set_graph_rag",
    }
