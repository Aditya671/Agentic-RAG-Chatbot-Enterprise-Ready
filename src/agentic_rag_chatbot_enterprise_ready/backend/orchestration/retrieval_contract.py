"""Small, dependency-free contract for agent retrieval configuration.

The agent currently uses Azure AI Search through LlamaIndex. This module keeps
retrieval policy explicit and independently testable so provider-specific
retrieval code does not become the source of truth for application behaviour.
"""
from __future__ import annotations

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

    def as_kwargs(self) -> dict[str, Any]:
        """Return the provider-facing retrieval keyword arguments."""
        return {
            "similarity_top_k": self.top_k,
            "vector_store_query_mode": self.query_mode,
        }
