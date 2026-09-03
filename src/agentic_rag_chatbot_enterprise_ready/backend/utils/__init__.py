"""Small deterministic backend utility functions."""
from __future__ import annotations

import json
from typing import Any


def to_millions(value: float) -> float:
    result = round(abs(value) / 1_000_000, 3)
    return result if value > 0 else -result


def to_thousands(value: float) -> float:
    result = round(abs(value) / 1_000, 2)
    return result if value > 0 else -result


def parse_response_sources(response_sources: Any) -> Any:
    """Normalize retriever source output without changing its payload shape."""
    if response_sources is None:
        return []
    if isinstance(response_sources, (list, dict)):
        return response_sources
    if isinstance(response_sources, str):
        value = response_sources.strip()
        if not value:
            return []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    raw_output = getattr(response_sources, "raw_output", None)
    if raw_output is not None and raw_output is not response_sources:
        return parse_response_sources(raw_output)
    return response_sources
