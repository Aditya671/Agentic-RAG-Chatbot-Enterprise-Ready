"""Incremental runtime integration for the compatibility agent."""
from __future__ import annotations

from typing import Any, Dict

from backend.orchestration.agentic_ai_system_upgraded import AsyncAgenticAiSystem
from backend.orchestration.execution_contract import AgentResponse, build_response
from backend.orchestration.retrieval_contract import RetrievalConfig
from backend.orchestration.runtime_boundary import AgentRuntimeBoundary


class IntegratedAsyncAgenticAiSystem(AsyncAgenticAiSystem):
    """Compatibility agent with stable retrieval and response contracts wired in."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        similarity_top_k = kwargs.get("similarity_top_k", 20)
        self.runtime_boundary = AgentRuntimeBoundary(RetrievalConfig(top_k=int(similarity_top_k)))
        super().__init__(*args, **kwargs)
        self._refresh_runtime_boundary()

    def _refresh_runtime_boundary(self) -> None:
        self.runtime_boundary = AgentRuntimeBoundary(RetrievalConfig(top_k=self.similarity_top_k))

    def set_similarity_top_k(self, similarity_top_k: int) -> None:
        super().set_similarity_top_k(similarity_top_k)
        self._refresh_runtime_boundary()

    def get_response_contract(self, response_block: Any) -> AgentResponse:
        return build_response(response_block, self.get_retriever_metadata(response_block))

    async def get_response(self, question: str) -> Dict[str, Any]:
        response = self.get_response_contract(await self.run_agent_async(question))
        return {"response_text": response.response_text, "response_metadata": response.response_metadata}

    def get_response_async(self, question: str) -> Dict[str, Any]:
        response_block = super().get_response_async(question)
        response = self.runtime_boundary.response(
            response_block.get("response_text", ""), response_block.get("response_metadata", [])
        )
        return {"response_text": response.response_text, "response_metadata": response.response_metadata}

    async def collect_response_stream(self, response: Any) -> str:
        return await self.runtime_boundary.collect_stream(self.stream_response(response))
