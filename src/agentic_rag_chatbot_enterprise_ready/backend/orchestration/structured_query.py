"""Structured-data query adapter."""
from __future__ import annotations

from typing import Any


class StructuredQueryEngine:
    """Build the existing pandas query capability behind a stable boundary."""

    def __init__(self, dataframe: Any, **kwargs: Any) -> None:
        try:
            from llama_index.experimental.query_engine.pandas import PandasQueryEngine
        except ImportError as exc:
            raise RuntimeError(
                "Structured CSV analysis requires the configured LlamaIndex pandas query engine."
            ) from exc
        self._engine = PandasQueryEngine(df=dataframe, **kwargs)

    def query(self, question: str) -> Any:
        return self._engine.query(question)

    async def aquery(self, question: str) -> Any:
        return await self._engine.aquery(question)

    @property
    def raw_engine(self) -> Any:
        return self._engine
