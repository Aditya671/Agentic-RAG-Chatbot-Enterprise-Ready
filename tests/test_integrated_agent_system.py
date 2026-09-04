from __future__ import annotations

import asyncio

from backend.orchestration.integrated_agent_system import IntegratedAsyncAgenticAiSystem


class TextResponse:
    text = "grounded answer"


class FakeIntegratedSystem:
    get_retriever_metadata = lambda self, response: ["doc-1"]

    def get_response_contract(self, response):
        return IntegratedAsyncAgenticAiSystem.get_response_contract(self, response)


def test_response_contract_preserves_retriever_metadata() -> None:
    result = FakeIntegratedSystem().get_response_contract(TextResponse())
    assert result.response_text == "grounded answer"
    assert result.response_metadata == ["doc-1"]


def test_stream_collection_uses_runtime_boundary() -> None:
    system = object.__new__(IntegratedAsyncAgenticAiSystem)

    async def chunks():
        yield "grounded "
        yield "answer"

    from backend.orchestration.runtime_boundary import AgentRuntimeBoundary
    system.runtime_boundary = AgentRuntimeBoundary()
    assert asyncio.run(system.collect_response_stream(chunks())) == "grounded answer"


def test_retrieval_policy_can_be_refreshed_without_provider_calls() -> None:
    system = object.__new__(IntegratedAsyncAgenticAiSystem)
    system.similarity_top_k = 17
    IntegratedAsyncAgenticAiSystem._refresh_runtime_boundary(system)
    assert system.runtime_boundary.retrieval.top_k == 17
    assert system.runtime_boundary.retrieval.query_mode == "semantic_hybrid"
