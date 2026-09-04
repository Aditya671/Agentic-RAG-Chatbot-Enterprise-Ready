from __future__ import annotations

import sys
import types

import pytest

from backend.orchestration.provider_boundaries import (
    build_retriever,
    build_structured_query_engine,
    resolve_query_mode,
)
from backend.orchestration.retrieval_contract import RetrievalConfig


class FakeIndex:
    def __init__(self) -> None:
        self.kwargs = None

    def as_retriever(self, **kwargs):
        self.kwargs = kwargs
        return kwargs


def test_build_retriever_translates_policy_at_provider_edge():
    index = FakeIndex()
    result = build_retriever(index, RetrievalConfig(top_k=13))

    assert result["similarity_top_k"] == 13
    assert result["vector_store_query_mode"].value == "hybrid"
    assert index.kwargs == result


def test_build_retriever_preserves_provider_specific_overrides():
    index = FakeIndex()
    result = build_retriever(
        index,
        RetrievalConfig(top_k=7),
        node_postprocessors=["reranker"],
    )

    assert result["similarity_top_k"] == 7
    assert result["node_postprocessors"] == ["reranker"]


def test_resolve_query_mode_rejects_unknown_values():
    with pytest.raises(ValueError, match="Unsupported retrieval query mode"):
        resolve_query_mode("unsupported")


def test_structured_factory_keeps_engine_dependency_behind_adapter(monkeypatch):
    fake_module = types.ModuleType("llama_index.experimental.query_engine.pandas")

    class FakePandasQueryEngine:
        def __init__(self, *, df, **kwargs):
            self.df = df
            self.kwargs = kwargs

    fake_module.PandasQueryEngine = FakePandasQueryEngine
    monkeypatch.setitem(sys.modules, "llama_index.experimental.query_engine.pandas", fake_module)

    engine = build_structured_query_engine([1, 2], engine_kwargs={"llm": "fake"})

    assert engine.raw_engine.df == [1, 2]
    assert engine.raw_engine.kwargs == {"llm": "fake"}
