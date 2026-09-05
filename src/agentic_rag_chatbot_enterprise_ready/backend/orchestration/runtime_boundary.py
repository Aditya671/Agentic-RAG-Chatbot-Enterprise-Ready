"""Provider-neutral runtime boundary for agent orchestration.

This module composes retrieval policy and response normalization into one small
application-facing boundary. Azure, LlamaIndex, and other provider objects stay
outside the contract itself.
"""
from __future__ import annotations

from collections.abc import AsyncIterable, Callable, Iterable
from typing import Any

from backend.orchestration.execution_contract import AgentResponse, build_response, collect_stream
from backend.orchestration.retrieval_contract import RetrievalConfig


class AgentRuntimeBoundary:
    """Coordinate stable retrieval and response contracts for an agent."""

    def __init__(self, retrieval: RetrievalConfig | None = None) -> None:
        self.retrieval = retrieval or RetrievalConfig()

    def retriever_kwargs(self, query_mode_resolver: Callable[[str], Any] | None = None) -> dict[str, Any]:
        """Build provider kwargs, optionally resolving the provider query-mode enum."""
        kwargs = self.retrieval.as_kwargs()
        if query_mode_resolver is not None:
            kwargs["vector_store_query_mode"] = query_mode_resolver(
                self.retrieval.query_mode
            )
        return kwargs

    def response(self, response: Any, metadata: Any = None) -> AgentResponse:
        """Normalize a provider response into the application response contract."""
        return build_response(response, metadata)

    async def collect_stream(self, chunks: AsyncIterable[Any] | Iterable[Any]) -> str:
        """Collect either sync or async provider response chunks."""
        return await collect_stream(chunks)
