from __future__ import annotations

import pandas as pd
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
    result = build_retriever(index, RetrievalConfig(top_k=7), node_postprocessors=["reranker"])
    assert result["similarity_top_k"] == 7
    assert result["node_postprocessors"] == ["reranker"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"similarity_top_k": 99},
        {"vector_store_query_mode": "default"},
        {"similarity_top_k": 99, "vector_store_query_mode": "default"},
    ],
)
def test_build_retriever_rejects_policy_overrides(kwargs):
    with pytest.raises(ValueError, match="Cannot override retrieval policy kwargs"):
        build_retriever(FakeIndex(), RetrievalConfig(top_k=7), **kwargs)


@pytest.mark.parametrize("value", [None, 1, True, "", "   "])
def test_resolve_query_mode_rejects_invalid_input_types(value):
    with pytest.raises(ValueError, match="query_mode"):
        resolve_query_mode(value)


def test_resolve_query_mode_rejects_unknown_values():
    with pytest.raises(ValueError, match="Unsupported retrieval query mode"):
        resolve_query_mode("unsupported")


def test_structured_factory_builds_native_pandas_engine():
    dataframe = pd.DataFrame({"asset": ["A", "B"], "noi": [100, 200]})
    engine = build_structured_query_engine(dataframe)
    assert engine.dataframe.equals(dataframe)
    assert engine.raw_engine is engine
