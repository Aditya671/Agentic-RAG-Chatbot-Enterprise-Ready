from __future__ import annotations

import asyncio

from backend.orchestration.runtime_boundary import AgentRuntimeBoundary


class TextResponse:
    text = "hello"


async def _chunks():
    yield "hel"
    yield "lo"


def test_retriever_kwargs_can_resolve_provider_enum_without_importing_provider() -> None:
    boundary = AgentRuntimeBoundary()

    result = boundary.retriever_kwargs(lambda value: f"MODE::{value}")

    assert result == {
        "similarity_top_k": 5,
        "vector_store_query_mode": "MODE::semantic_hybrid",
    }


def test_custom_retrieval_policy_reaches_provider_boundary() -> None:
    from backend.orchestration.retrieval_contract import RetrievalConfig

    boundary = AgentRuntimeBoundary(RetrievalConfig(top_k=17))
    result = boundary.retriever_kwargs(str.upper)

    assert result["similarity_top_k"] == 17
    assert result["vector_store_query_mode"] == "SEMANTIC_HYBRID"


def test_response_normalization_is_provider_neutral() -> None:
    boundary = AgentRuntimeBoundary()

    response = boundary.response(TextResponse(), {"sources": ["doc-1"]})

    assert response.response_text == "hello"
    assert response.response_metadata == {"sources": ["doc-1"]}


def test_async_stream_is_collected_without_pytest_asyncio() -> None:
    boundary = AgentRuntimeBoundary()

    result = asyncio.run(boundary.collect_stream(_chunks()))

    assert result == "hello"


def test_sync_stream_is_collected() -> None:
    boundary = AgentRuntimeBoundary()

    result = asyncio.run(boundary.collect_stream(["a", "", "b"]))

    assert result == "ab"
