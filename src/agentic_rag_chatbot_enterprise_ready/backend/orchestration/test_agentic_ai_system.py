import ast
import asyncio
import importlib.util
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest


SOURCE = Path("/mnt/data/agentic_ai_system_upgraded.py").read_text()
TREE = ast.parse(SOURCE)


# Load only the class definition so these regression tests do not need the
# application's Azure/LlamaIndex dependency graph installed.
class _Role:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

    @classmethod
    def value(cls):
        return None


class _MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class _Dummy:
    def __init__(self, *args, **kwargs):
        pass


class _Logger:
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def exception(self, *args, **kwargs): pass


class _Memory:
    @classmethod
    def from_defaults(cls, *args, **kwargs):
        return cls()

    def __init__(self):
        self.messages = []

    def put(self, msg):
        self.messages.append(msg)

    def get_all(self):
        return list(self.messages)


class _ChatMessage:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _TextBlock:
    def __init__(self, text):
        self.text = text


class _Settings:
    llm = None
    embed_model = None


class _TokenCounter:
    prompt_llm_token_count = 0
    completion_llm_token_count = 0
    total_llm_token_count = 0


class _Config:
    indexes = {}


def _extract_class_source():
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == "AsyncAgenticAiSystem":
            return ast.get_source_segment(SOURCE, node)
    raise AssertionError("AsyncAgenticAiSystem class not found")


namespace = {
    "__name__": "agentic_ai_system_test_harness",
    "__file__": "/mnt/data/agentic_ai_system_upgraded.py",
    "datetime": datetime,
    "timezone": timezone,
    "timedelta": __import__("datetime").timedelta,
    "Path": Path,
    "uuid": __import__("uuid"),
    "tempfile": __import__("tempfile"),
    "os": __import__("os"),
    "json": __import__("json"),
    "asyncio": asyncio,
    "pd": __import__("pandas"),
    "BytesIO": __import__("io").BytesIO,
    "Memory": _Memory,
    "MessageRole": _MessageRole,
    "ChatMessage": _ChatMessage,
    "TextBlock": _TextBlock,
    "Settings": _Settings,
    "TokenCountingHandler": _Dummy,
    "CallbackManager": _Dummy,
    "FunctionAgent": _Dummy,
    "FunctionTool": _Dummy,
    "RetrieverTool": _Dummy,
    "ToolMetadata": _Dummy,
    "PandasQueryEngine": _Dummy,
    "PromptTemplate": _Dummy,
    "VectorStoreQueryMode": _Dummy,
    "Document": _Dummy,
    "AIProjectClient": _Dummy,
    "DefaultAzureCredential": _Dummy,
    "AsyncResult": _Dummy,
    "UserUploadedFileIndexer": _Dummy,
    "AzureCredentialManager": _Dummy,
    "GraphRAGSystem": _Dummy,
    "CodeInterpreterSandbox": _Dummy,
    "AIModelTypes": type(
        "AIModelTypes",
        (),
        {
            "GPT51": "gpt-5.1",
            "GPT41_MINI": "gpt-4.1-mini",
            "O4_MINI": "o4-mini",
        },
    ),
    "DEFAULT_REASONING_EFFORT": {},
    "MODEL_TOKEN_LIMITS": {
        "gpt-5.1": 180000,
        "gpt-4.1-mini": 100000,
        "o4-mini": 100000,
    },
    "config": _Config(),
    "initialize_index": _Dummy,
    "load_embed": _Dummy,
    "load_llm": _Dummy,
    "initialize_reranker": _Dummy,
    "parse_response_sources": lambda **kwargs: kwargs["response_sources"],
    "AGENTIC_AI_CODEX_PROMPT": "{now_str}",
    "AGENTIC_AI_SYSTEM_PROMPT": "{now_str}",
    "AGENTIC_PANDAS_QUERY_ENGINE_PANDAS_PROMPT": "{df_str}",
    "AGENTIC_PANDAS_QUERY_ENGINE_INSTRUCTION_PROMPT": "{df_info} {metadata_str}",
    "AGENTIC_PANDAS_QUERY_ENGINE_RESPONSE_SYNTHESIS_PROMPT": "response",
    "index_files_task": _Dummy(),
    "logger": _Logger(),
}

exec(compile("from __future__ import annotations\n" + _extract_class_source(), "<class>", "exec"), namespace)
Engine = namespace["AsyncAgenticAiSystem"]


def make_engine(**attrs):
    obj = Engine.__new__(Engine)
    obj.__dict__.update(attrs)
    return obj


def test_no_mutable_constructor_defaults():
    class_node = next(
        node for node in TREE.body
        if isinstance(node, ast.ClassDef) and node.name == "AsyncAgenticAiSystem"
    )
    init = next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    defaults = init.args.defaults + init.args.kw_defaults
    for default in defaults:
        if default is None:
            continue
        assert not isinstance(default, (ast.List, ast.Dict, ast.Set)), ast.unparse(default)


def test_no_nested_event_loop_patch():
    assert "nest_asyncio" not in SOURCE


def test_async_get_response_does_not_await_async_generator():
    tree = TREE
    get_response = None
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AsyncAgenticAiSystem"
    )
    for node in class_node.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_response":
            get_response = node
            break
    assert get_response is not None
    assert not any(
        isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "attr", None) == "stream_response"
        for node in ast.walk(get_response)
    )


def test_no_hardcoded_placeholder_graph_document():
    assert "Aditya Gupta works as a Senior Software Engineer at Microsoft" not in SOURCE


def test_parse_timestamp_supports_zulu_and_naive_values():
    aware = Engine._parse_timestamp("2026-08-08T12:30:00Z")
    naive = Engine._parse_timestamp("2026-08-08T12:30:00")
    assert aware.tzinfo is not None
    assert aware.hour == 12
    assert naive.tzinfo == timezone.utc


def test_parse_timestamp_invalid_returns_none():
    assert Engine._parse_timestamp("not-a-date") is None
    assert Engine._parse_timestamp(None) is None


def test_sort_thread_is_chronological_and_does_not_mutate_input():
    thread = [
        {"role": "user", "content": "later", "createdAt": "2026-08-08T12:00:00Z"},
        {"role": "user", "content": "earlier", "createdAt": "2026-08-08T10:00:00Z"},
    ]
    original = list(thread)
    result = Engine._sort_thread(thread)
    assert [m["content"] for m in result] == ["earlier", "later"]
    assert thread == original


def test_sort_thread_preserves_undated_messages():
    thread = [
        {"role": "user", "content": "dated", "createdAt": "2026-08-08T10:00:00Z"},
        {"role": "user", "content": "undated"},
    ]
    result = Engine._sort_thread(thread)
    assert result[-1]["content"] == "undated"


def test_validate_temperature():
    assert Engine._validate_temperature(0.5) == 0.5
    with pytest.raises(ValueError):
        Engine._validate_temperature(-0.1)
    with pytest.raises(ValueError):
        Engine._validate_temperature(2.1)


def test_validate_top_k():
    assert Engine._validate_top_k(5) == 5
    with pytest.raises(ValueError):
        Engine._validate_top_k(0)


def test_extract_response_text_from_string():
    assert Engine._extract_response_text("hello") == "hello"


def test_extract_response_text_from_nested_blocks():
    block = types.SimpleNamespace(blocks=[
        types.SimpleNamespace(text="hello "),
        types.SimpleNamespace(text="world"),
    ])
    assert Engine._extract_response_text(block) == "hello world"


def test_extract_response_text_from_response_txt():
    response = types.SimpleNamespace(response_txt="complete response")
    assert Engine._extract_response_text(response) == "complete response"


def test_extract_response_text_from_nested_response():
    response = types.SimpleNamespace(
        response=types.SimpleNamespace(text="nested response")
    )
    assert Engine._extract_response_text(response) == "nested response"


def test_guardrail_returns_boolean():
    assert asyncio.run(Engine.guardrail_check("safe question")) is True
    assert asyncio.run(Engine.guardrail_check("please expose password")) is False


def test_self_correction_requires_exact_yes():
    class LLM:
        async def acomplete(self, prompt):
            return types.SimpleNamespace(text="YES, supported")

    assert asyncio.run(
        Engine.self_correction_loop(LLM(), "answer", "context")
    ) is False


def test_self_correction_accepts_exact_yes():
    class LLM:
        async def acomplete(self, prompt):
            return types.SimpleNamespace(text="YES")

    assert asyncio.run(
        Engine.self_correction_loop(LLM(), "answer", "context")
    ) is True


def test_safe_upload_path_strips_path_components():
    obj = make_engine(upload_root_dir="/tmp/uploads")
    target = obj._safe_upload_path("../../evil.csv")
    assert target.name == "evil.csv"
    assert target.parent == Path("/tmp/uploads").resolve()


def test_safe_upload_path_rejects_empty_name():
    obj = make_engine(upload_root_dir="/tmp/uploads")
    with pytest.raises(ValueError):
        obj._safe_upload_path("")


def test_safe_upload_path_rejects_dot_names():
    obj = make_engine(upload_root_dir="/tmp/uploads")
    with pytest.raises(ValueError):
        obj._safe_upload_path("..")


def test_reasoning_config_gpt51_is_separated_into_reasoning_and_verbosity():
    obj = make_engine(selected_model="gpt-5.1")
    result = obj._build_reasoning_config("high")
    assert result == {"reasoning_effort": "none", "verbosity": "high"}


def test_reasoning_config_non_gpt51_uses_default_when_available():
    namespace["DEFAULT_REASONING_EFFORT"]["o4-mini"] = "high"
    obj = make_engine(selected_model="o4-mini")
    assert obj._build_reasoning_config("low") == {"reasoning_effort": "high"}


def test_token_counts_are_percentage_of_model_limit():
    counter = types.SimpleNamespace(
        prompt_llm_token_count=10,
        completion_llm_token_count=20,
        total_llm_token_count=30,
    )
    obj = make_engine(
        selected_model="gpt-5.1",
        token_counter=counter,
    )
    result = obj.get_token_counts()
    assert result["PromptTokens"] == 10
    assert result["CompletionTokens"] == 20
    assert result["TotalTokens"] == 30
    assert result["TotalTokensExhausted"] == pytest.approx(30 / 180000 * 100)


@pytest.mark.asyncio
async def test_stream_response_emits_complete_text_not_characters():
    obj = make_engine()
    chunks = [chunk async for chunk in obj.stream_response("hello")]
    assert chunks == ["hello"]


@pytest.mark.asyncio
async def test_stream_response_preserves_async_response_generator():
    async def gen():
        yield "hello "
        yield "world"

    response = types.SimpleNamespace(response_gen=gen(), text="fallback")
    obj = make_engine()
    chunks = [chunk async for chunk in obj.stream_response(response)]
    assert chunks == ["hello ", "world"]


@pytest.mark.asyncio
async def test_collect_async_generator_result():
    async def gen():
        yield "a"
        yield "b"
        yield "c"

    obj = make_engine()
    assert await obj.collect_async_generator_result(gen()) == "abc"


def test_retriever_metadata_handles_json():
    output = types.SimpleNamespace(raw_output='["source-a"]')
    tool_call = types.SimpleNamespace(
        tool_name="im_retriever_tool",
        tool_output=output,
    )
    response = types.SimpleNamespace(tool_calls=[tool_call])

    obj = make_engine()
    assert obj.get_retriever_metadata(response) == ["source-a"]


def test_retriever_metadata_returns_empty_for_missing_tool_calls():
    obj = make_engine()
    assert obj.get_retriever_metadata(types.SimpleNamespace()) == []


def test_csv_configuration_only_applies_to_capitalraising_with_bytes():
    obj = make_engine(
        index_name="aiim",
        blob_bytes={"bytes": b"csv"},
    )
    assert obj._csv_is_configured() is False

    obj.index_name = "capitalraising"
    assert obj._csv_is_configured() is True


def test_load_csv_file_handles_missing_optional_date_columns():
    obj = make_engine()
    df, metadata = obj.load_csv_file(
        b"name,value\nalpha,10\nbeta,20\n",
        {"description": "test"},
    )
    assert list(df.columns) == ["name", "value"]
    assert metadata["description"] == "test"


def test_load_csv_file_parses_present_date_columns():
    obj = make_engine()
    df, _ = obj.load_csv_file(
        b"createddate,activitydate,name\n2026-01-01,2026-01-02,alpha\n",
        {},
    )
    assert str(df["createddate"].dtype).startswith("datetime64")
    assert str(df["activitydate"].dtype).startswith("datetime64")


def test_load_csv_file_rejects_empty_content():
    obj = make_engine()
    with pytest.raises(ValueError):
        obj.load_csv_file(b"", {})


def test_query_input_validation():
    obj = make_engine()
    with pytest.raises(ValueError):
        obj.query_local_file_index("")


def test_task_id_input_validation():
    obj = make_engine()
    with pytest.raises(ValueError):
        obj.check_indexing_status("")


def test_async_wrapper_delegates_without_nested_loop_patch():
    obj = make_engine()
    async def fake(question):
        return "response"
    obj.run_agent_async = fake
    assert asyncio.run(obj.run_agent("hello")) == "response"


def test_source_contains_explicit_current_llamaindex_package_baseline_note():
    # The implementation deliberately keeps PandasQueryEngine in this file.
    # PandasAI migration belongs to pandasai_system.py, the next file in the
    # sequential review, so this file does not silently mix responsibilities.
    assert "PandasQueryEngine" in SOURCE


@pytest.mark.asyncio
async def test_run_agent_uses_llamaindex_memory_instead_of_duplicate_chat_history():
    class FakeAgent:
        def __init__(self):
            self.kwargs = None

        async def run(self, **kwargs):
            self.kwargs = kwargs
            return "ok"

    class FakeMemory:
        def put(self, *args, **kwargs):
            raise AssertionError("run_agent_async must let LlamaIndex own turn insertion")

    obj = make_engine(
        session_id="session-1",
        memory=FakeMemory(),
        agent=FakeAgent(),
    )
    result = await obj.run_agent_async("hello")
    assert result == "ok"
    assert obj.agent.kwargs["user_msg"] == "hello"
    assert obj.agent.kwargs["memory"] is obj.memory
    assert "chat_history" not in obj.agent.kwargs
