"""Provider-neutral construction of optional agent runtime components."""
from __future__ import annotations

from typing import Any, Callable


def build_reranker(
    *,
    enabled: bool,
    llm: Any,
    top_n: int,
    initialize: Callable[..., Any],
    logger: Any,
) -> Any | None:
    """Build the optional reranker without coupling orchestration to its provider."""
    if not enabled:
        return None
    try:
        return initialize(llm=llm, top_n=top_n)
    except Exception:
        logger.exception("[AgenticAi] Reranker initialization failed; disabling it")
        return None


def build_graph_rag(
    *,
    enabled: bool,
    llm: Any,
    embed_model: Any,
    initialize: Callable[..., Any],
    logger: Any,
) -> Any | None:
    """Build optional GraphRAG while preserving fail-open behavior."""
    if not enabled:
        return None
    try:
        return initialize(llm=llm, embed_model=embed_model)
    except Exception:
        logger.exception("[AgenticAi] GraphRAG initialization failed; disabling it")
        return None


def build_code_interpreter(
    *,
    enabled: bool,
    initialize: Callable[[], Any],
    logger: Any,
) -> Any | None:
    """Build optional code execution while preserving fail-closed availability."""
    if not enabled:
        return None
    try:
        return initialize()
    except Exception:
        logger.exception("[AgenticAi] Code interpreter initialization failed")
        return None
