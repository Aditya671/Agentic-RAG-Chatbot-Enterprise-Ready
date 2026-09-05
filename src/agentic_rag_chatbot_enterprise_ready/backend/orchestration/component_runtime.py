"""Provider-neutral construction of optional agent runtime components."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_reranker(*, enabled: bool, llm: Any, top_n: int, initialize: Callable[..., Any], logger: Any) -> Any | None:
    if not enabled:
        return None
    try:
        return initialize(llm=llm, top_n=top_n)
    except Exception:
        logger.exception("[AgenticAi] Reranker initialization failed; disabling it")
        return None


def build_graph_rag(*, enabled: bool, llm: Any, embed_model: Any, initialize: Callable[..., Any], logger: Any) -> Any | None:
    if not enabled:
        return None
    try:
        return initialize(llm=llm, embed_model=embed_model)
    except Exception:
        logger.exception("[AgenticAi] GraphRAG initialization failed; disabling it")
        return None


def build_code_interpreter(*, enabled: bool, initialize: Callable[[], Any], logger: Any) -> None:
    """Retained only as a compatibility no-op; arbitrary code execution is removed."""
    if enabled:
        logger.warning("[AgenticAi] Code execution was requested but is no longer supported")
    return None
