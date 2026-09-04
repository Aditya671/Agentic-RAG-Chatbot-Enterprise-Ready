"""Provider-neutral validation for runtime retrieval policy."""
from __future__ import annotations


def validate_top_k(value: int) -> int:
    """Validate retrieval depth without coercing unrelated input types."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("similarity_top_k must be an integer")
    if value < 1:
        raise ValueError("similarity_top_k must be >= 1")
    return value
