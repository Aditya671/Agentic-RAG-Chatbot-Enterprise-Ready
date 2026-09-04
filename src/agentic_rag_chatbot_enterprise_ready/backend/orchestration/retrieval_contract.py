"""Dependency-light contract for agent retrieval configuration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    """Validated retrieval policy shared by agent orchestration code."""

    top_k: int = 5
    query_mode: str = "semantic_hybrid"

    def __post_init__(self) -> None:
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int):
            raise ValueError("top_k must be an integer")
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if not isinstance(self.query_mode, str) or not self.query_mode.strip():
            raise ValueError("query_mode must be a non-empty string")
        if self.query_mode.strip().casefold() != "semantic_hybrid":
            raise ValueError("query_mode must be 'semantic_hybrid'")

    def as_kwargs(self) -> dict[str, Any]:
        """Return provider-facing retrieval kwargs without importing a provider SDK."""
        return {
            "similarity_top_k": self.top_k,
            "vector_store_query_mode": self.query_mode,
        }

    def resolve_query_mode(self, resolver: Callable[[str], Any]) -> Any:
        """Resolve the provider query-mode value at the integration boundary."""
        if not callable(resolver):
            raise TypeError("resolver must be callable")
        return resolver(self.query_mode)
