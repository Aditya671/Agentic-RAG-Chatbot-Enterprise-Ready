"""Regression coverage for behavior retained by the migration runtime.

These tests intentionally load only the ``AsyncAgenticAiSystem`` class body from
its compatibility source. They therefore validate pure helpers without requiring
Azure credentials or constructing provider clients during test collection.
"""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "agentic_rag_chatbot_enterprise_ready"
    / "backend"
    / "orchestration"
    / "agentic_ai_system_upgraded.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


class _MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class _Memory:
    @classmethod
    def from_defaults(cls, *args, **kwargs):
        return cls()

    def put(self, message):
        return None


class _ChatMessage:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _TextBlock:
    def __init__(self, text):
        self.text = text


class _ModelTypes:
    GPT51 = "gpt-5.1"
    GPT41_MINI = "gpt-4.1-mini"
    O4_MINI = "o4-mini"

    def __new__(cls, value):
        return value


class _Dummy:
    pass


namespace = {
    "__name__": "legacy_runtime_regression_harness",
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
    "Settings": _Dummy,
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
    "AIModelTypes": _ModelTypes,
    "DEFAULT_REASONING_EFFORT": {},
    "MODEL_TOKEN_LIMITS": {
        "gpt-5.1": 180000,
        "gpt-4.1-mini": 100000,
        "o4-mini": 100000,
    },
    "config": _Dummy(),
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
    "logger": _Dummy(),
}


class_node = next(
    node for node in TREE.body
    if isinstance(node, ast.ClassDef) and node.name == "AsyncAgenticAiSystem"
)
class_source = ast.get_source_segment(SOURCE, class_node)
exec(compile("from __future__ import annotations\n" + class_source, "<class>", "exec"), namespace)
Engine = namespace["AsyncAgenticAiSystem"]


def make_engine(**attrs):
    obj = Engine.__new__(Engine)
    obj.__dict__.update(attrs)
    return obj


def test_source_is_loaded_from_repository_not_external_temp_path():
    assert SOURCE_PATH.exists()
    assert "/mnt/data/" not in str(SOURCE_PATH)


def test_parse_timestamp_supports_zulu_and_naive_values():
    aware = Engine._parse_timestamp("2026-08-08T12:30:00Z")
    naive = Engine._parse_timestamp("2026-08-08T12:30:00")
    assert aware.tzinfo is not None
    assert aware.hour == 12
    assert naive.tzinfo == timezone.utc


def test_sort_thread_is_chronological_without_mutating_input():
    thread = [
        {"role": "user", "content": "later", "createdAt": "2026-08-08T12:00:00Z"},
        {"role": "user", "content": "earlier", "createdAt": "2026-08-08T10:00:00Z"},
    ]
    original = list(thread)
    result = Engine._sort_thread(thread)
    assert [item["content"] for item in result] == ["earlier", "later"]
    assert thread == original


def test_extract_response_text_handles_nested_response_and_blocks():
    response = SimpleNamespace(
        response=SimpleNamespace(
            blocks=[SimpleNamespace(text="hello "), SimpleNamespace(text="world")]
        )
    )
    assert Engine._extract_response_text(response) == "hello world"


def test_safe_upload_path_removes_client_path_components():
    obj = make_engine(upload_root_dir="/tmp/uploads")
    target = obj._safe_upload_path("../../evil.csv")
    assert target.name == "evil.csv"
    assert target.parent == Path("/tmp/uploads").resolve()


def test_safe_upload_path_rejects_empty_name():
    obj = make_engine(upload_root_dir="/tmp/uploads")
    with pytest.raises(ValueError):
        obj._safe_upload_path("")


def test_validate_top_k_rejects_zero():
    assert Engine._validate_top_k(5) == 5
    with pytest.raises(ValueError):
        Engine._validate_top_k(0)


def test_csv_configuration_is_scoped_to_capitalraising_with_payload():
    obj = make_engine(index_name="aiim", blob_bytes={"bytes": b"csv"})
    assert obj._csv_is_configured() is False
    obj.index_name = "capitalraising"
    assert obj._csv_is_configured() is True


@pytest.mark.asyncio
async def test_stream_response_does_not_split_plain_text_into_characters():
    obj = make_engine()
    chunks = [chunk async for chunk in obj.stream_response("hello")]
    assert chunks == ["hello"]
