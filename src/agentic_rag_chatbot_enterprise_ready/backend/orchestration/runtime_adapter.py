"""Integration adapter for the existing agent runtime.

The large compatibility agent remains responsible for provider-specific setup.
This adapter makes its execution surface consume the stable Phase 7 contracts
without forcing a wholesale rewrite of the orchestration implementation.
"""
from __future__ import annotations

from collections.abc import AsyncIterable, Iterable
from typing import Any, Protocol

from backend.orchestration.execution_contract import AgentResponse, build_response, collect_stream
from backend.orchestration.retrieval_contract import RetrievalConfig
from backend.orchestration.runtime_boundary import AgentRuntimeBoundary


class AgentExecutor(Protocol):
    """Minimal execution surface required by the adapter."""

    async def run_agent_async(self, question: str) -> Any: ...

    def stream_response(self, question: str) -> AsyncIterable[Any] | Iterable[Any]: ...


class AgentRuntimeAdapter:
    """Apply application contracts around an existing agent executor."""

    def __init__(self, executor: AgentExecutor, retrieval: RetrievalConfig | None = None) -> None:
        if executor is None:
            raise ValueError("executor is required")
        self.executor = executor
        self.boundary = AgentRuntimeBoundary(retrieval)

    @property
    def retrieval_kwargs(self) -> dict[str, Any]:
        """Return provider-facing retrieval policy for the integration layer."""
        return self.boundary.retriever_kwargs()

    async def run(self, question: str, metadata: Any = None) -> AgentResponse:
        """Execute one turn and normalize the provider response."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        response = await self.executor.run_agent_async(question)
        return build_response(response, metadata)

    async def stream(self, question: str) -> str:
        """Execute the existing streaming surface and normalize its output."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        chunks = self.executor.stream_response(question)
        return await collect_stream(chunks)
