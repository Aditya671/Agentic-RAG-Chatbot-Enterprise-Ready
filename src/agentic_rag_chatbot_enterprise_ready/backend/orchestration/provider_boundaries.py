"""Provider-edge factories for retrieval and structured querying.

Application policy stays provider-neutral in ``AgentRuntimeBoundary`` and
``RetrievalConfig``. This module is the narrow place where that policy is
translated into LlamaIndex/Azure-facing objects.
"""
from __future__ import annotations

from typing import Any, Mapping

from backend.orchestration.retrieval_contract import RetrievalConfig
from backend.orchestration.structured_query import StructuredQueryEngine


_PROTECTED_RETRIEVAL_KWARGS = frozenset(
    {"similarity_top_k", "vector_store_query_mode"}
)


def resolve_query_mode(query_mode: str) -> Any:
    """Resolve an application query-mode name at the LlamaIndex boundary."""
    if not isinstance(query_mode, str) or not query_mode.strip():
        raise ValueError("query_mode must be a non-empty string")

    from llama_index.core.vector_stores.types import VectorStoreQueryMode

    normalized = query_mode.strip().lower()
    mapping = {
        "default": VectorStoreQueryMode.DEFAULT,
        "sparse": VectorStoreQueryMode.SPARSE,
        "dense": VectorStoreQueryMode.DEFAULT,
        "semantic_hybrid": VectorStoreQueryMode.SEMANTIC_HYBRID,
        "hybrid": VectorStoreQueryMode.SEMANTIC_HYBRID,
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported retrieval query mode: {query_mode!r}") from exc


def _merge_provider_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Reject provider kwargs that would bypass validated retrieval policy."""
    protected = _PROTECTED_RETRIEVAL_KWARGS.intersection(kwargs)
    if protected:
        names = ", ".join(sorted(protected))
        raise ValueError(f"Cannot override retrieval policy kwargs: {names}")
    return dict(kwargs)


def build_retriever(index: Any, retrieval: RetrievalConfig, **kwargs: Any) -> Any:
    """Build a LlamaIndex retriever from validated application retrieval policy."""
    if index is None:
        raise ValueError("index cannot be None")

    provider_kwargs = retrieval.as_kwargs()
    provider_kwargs["vector_store_query_mode"] = resolve_query_mode(retrieval.query_mode)
    provider_kwargs.update(_merge_provider_kwargs(**kwargs))
    return index.as_retriever(**provider_kwargs)


def build_structured_query_engine(
    dataframe: Any,
    *,
    engine_kwargs: Mapping[str, Any] | None = None,
) -> StructuredQueryEngine:
    """Create the supported structured-query adapter at the provider edge."""
    return StructuredQueryEngine(dataframe, engine_kwargs=engine_kwargs)
