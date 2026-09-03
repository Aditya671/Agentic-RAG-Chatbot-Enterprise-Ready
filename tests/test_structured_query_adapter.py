"""Contract tests for the structured-query boundary."""
from __future__ import annotations

import asyncio
import importlib
import sys
import types

import pytest


class _FakeEngine:
    def __init__(self, *, df, **kwargs):
        self.df = df
        self.kwargs = kwargs
        self.calls: list[str] = []

    def query(self, question: str):
        self.calls.append(question)
        return {"question": question, "rows": len(self.df)}


def _load_adapter(monkeypatch: pytest.MonkeyPatch):
    fake_module = types.ModuleType("llama_index.experimental.query_engine.pandas")
    fake_module.PandasQueryEngine = _FakeEngine

    for name in (
        "llama_index.experimental.query_engine.pandas",
        "llama_index.experimental.query_engine",
        "llama_index.experimental",
    ):
        module = types.ModuleType(name)
        monkeypatch.setitem(sys.modules, name, module)

    sys.modules["llama_index.experimental.query_engine.pandas"] = fake_module
    return importlib.import_module(
        "agentic_rag_chatbot_enterprise_ready.backend.orchestration.structured_query"
    )


def test_adapter_preserves_engine_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_adapter(monkeypatch)
    engine = module.StructuredQueryEngine([1, 2, 3], engine_kwargs={"foo": "bar"})

    assert engine.raw_engine.df == [1, 2, 3]
    assert engine.raw_engine.kwargs == {"foo": "bar"}
    assert engine.query("count rows") == {"question": "count rows", "rows": 3}


@pytest.mark.parametrize("question", ["", "   ", None])
def test_adapter_rejects_empty_questions(monkeypatch: pytest.MonkeyPatch, question) -> None:
    module = _load_adapter(monkeypatch)
    engine = module.StructuredQueryEngine([])

    with pytest.raises(ValueError, match="non-empty"):
        engine.query(question)


def test_async_query_uses_non_blocking_adapter_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_adapter(monkeypatch)
    engine = module.StructuredQueryEngine([1, 2])

    result = asyncio.run(engine.aquery("sum"))

    assert result == {"question": "sum", "rows": 2}
    assert engine.raw_engine.calls == ["sum"]
