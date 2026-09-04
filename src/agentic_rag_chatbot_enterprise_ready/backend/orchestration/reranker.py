from __future__ import annotations

import logging
from typing import Any, Optional

from llama_index.core.llms import LLM
from llama_index.core.postprocessor import LLMRerank

logger = logging.getLogger(__name__)


class RerankerConfigurationError(ValueError):
    """Raised when reranker configuration is invalid."""


def _validate_positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RerankerConfigurationError(f"{name} must be a positive integer.")
    if value < 1:
        raise RerankerConfigurationError(f"{name} must be >= 1.")
    return value


def initialize_reranker(
    llm: LLM,
    top_n: int = 5,
    choice_batch_size: int = 5,
    *,
    callback_manager: Optional[Any] = None,
    choice_select_prompt: Optional[Any] = None,
) -> LLMRerank:
    """Create a validated LlamaIndex LLM-based reranker.

    The application performs first-stage retrieval elsewhere and attaches this
    object as a LlamaIndex node postprocessor. ``LLMRerank`` then performs
    second-stage relevance selection over the retrieved candidates.

    Args:
        llm: LlamaIndex-compatible LLM used to score/select candidates.
        top_n: Maximum number of candidates returned after reranking.
        choice_batch_size: Number of candidates presented to the LLM per
            reranking call.
        callback_manager: Optional LlamaIndex callback manager for observability.
        choice_select_prompt: Optional custom LlamaIndex reranking prompt.

    Returns:
        A configured ``LLMRerank`` postprocessor.

    Raises:
        RerankerConfigurationError: If arguments are invalid.
        RuntimeError: If LlamaIndex cannot construct the postprocessor.

    Notes:
        ``LLMRerank`` is intentionally kept as the implementation here rather
        than replacing it with a different reranker. The current LlamaIndex
        core API still exposes it as a node postprocessor, and the application
        already integrates it through ``node_postprocessors``.
    """
    if llm is None:
        raise RerankerConfigurationError("llm is required.")

    top_n = _validate_positive_int(top_n, "top_n")
    choice_batch_size = _validate_positive_int(
        choice_batch_size,
        "choice_batch_size",
    )

    kwargs: dict[str, Any] = {
        "llm": llm,
        "top_n": top_n,
        "choice_batch_size": choice_batch_size,
    }

    if callback_manager is not None:
        kwargs["callback_manager"] = callback_manager

    if choice_select_prompt is not None:
        kwargs["choice_select_prompt"] = choice_select_prompt

    try:
        reranker = LLMRerank(**kwargs)
    except Exception as exc:
        logger.exception(
            "Failed to initialize LlamaIndex LLMRerank "
            "(top_n=%d, choice_batch_size=%d).",
            top_n,
            choice_batch_size,
        )
        raise RuntimeError("Failed to initialize the LlamaIndex reranker.") from exc

    logger.info(
        "LlamaIndex LLMRerank initialized: top_n=%d, choice_batch_size=%d",
        top_n,
        choice_batch_size,
    )
    return reranker
