from __future__ import annotations

import asyncio

import pytest

from backend.orchestration.runtime_adapter import AgentRuntimeAdapter


class Response:
    text = "answer"


class FakeExecutor:
    async def run_agent_async(self, question: str):
        return Response()

    def stream_response(self, question: str):
        return ["an", "swer"]


def test_adapter_exposes_retrieval_policy():
    adapter = AgentRuntimeAdapter(FakeExecutor())

    assert adapter.retrieval_kwargs == {
        "similarity_top_k": 5,
        "vector_store_query_mode": "semantic_hybrid",
    }


def test_adapter_normalizes_async_execution():
    adapter = AgentRuntimeAdapter(FakeExecutor())

    result = asyncio.run(adapter.run("question", {"source": "doc"}))

    assert result.response_text == "answer"
    assert result.response_metadata == {"source": "doc"}


def test_adapter_normalizes_streaming_execution():
    adapter = AgentRuntimeAdapter(FakeExecutor())

    assert asyncio.run(adapter.stream("question")) == "answer"


@pytest.mark.parametrize("question", ["", "   ", None])
def test_adapter_rejects_invalid_questions(question):
    adapter = AgentRuntimeAdapter(FakeExecutor())

    with pytest.raises(ValueError):
        asyncio.run(adapter.run(question))

    with pytest.raises(ValueError):
        asyncio.run(adapter.stream(question))


def test_adapter_requires_executor():
    with pytest.raises(ValueError):
        AgentRuntimeAdapter(None)
