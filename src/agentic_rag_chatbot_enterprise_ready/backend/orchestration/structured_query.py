"""Stable boundary for structured-data querying.

The application currently uses LlamaIndex's experimental PandasQueryEngine for
CSV analysis. Keeping that dependency behind this adapter lets the rest of the
agent remain independent of the experimental package and gives us one place to
replace it when a supported structured-query implementation is adopted.
"""
from __future__ import annotations

import asyncio
from typing import Any, Mapping


class StructuredQueryEngine:
    """Compatibility adapter around the current structured-query engine."""

    def __init__(self, dataframe: Any, *, engine_kwargs: Mapping[str, Any] | None = None) -> None:
        try:
            from llama_index.experimental.query_engine.pandas import PandasQueryEngine
        except ImportError as exc:
            raise RuntimeError(
                "Structured CSV analysis requires the configured LlamaIndex pandas "
                "query engine. Install the project's structured-query dependency."
            ) from exc

        kwargs = dict(engine_kwargs or {})
        self._engine = PandasQueryEngine(df=dataframe, **kwargs)

    def query(self, question: str) -> Any:
        """Execute a structured query synchronously."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        return self._engine.query(question)

    async def aquery(self, question: str) -> Any:
        """Execute a structured query without blocking the event loop.

        The experimental engine's async surface has changed across releases,
        so the adapter deliberately uses the stable synchronous contract in a
        worker thread rather than depending on an optional ``aquery`` method.
        """
        return await asyncio.to_thread(self.query, question)

    @property
    def raw_engine(self) -> Any:
        """Expose the underlying engine for narrowly scoped compatibility use."""
        return self._engine
