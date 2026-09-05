"""Stable response boundary for agent execution.

Provider SDK response objects are intentionally kept behind this small module so
callers can consume plain application data without depending on LlamaIndex
response internals.
"""
from __future__ import annotations

from collections.abc import AsyncIterable, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Application-level response produced by an agent turn."""

    response_text: str
    response_metadata: Any


def extract_text(response: Any) -> str:
    """Normalize common agent response representations to text."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response

    nested = getattr(response, "response", None)
    if nested is not None and nested is not response:
        text = extract_text(nested)
        if text:
            return text

    for attr in ("text", "response_txt", "content"):
        value = getattr(response, attr, None)
        if value:
            return str(value)

    blocks = getattr(response, "blocks", None)
    if blocks:
        parts = [str(block.text) for block in blocks if getattr(block, "text", None)]
        if parts:
            return "".join(parts)

    return str(response)


def build_response(response: Any, metadata: Any) -> AgentResponse:
    """Build the stable public response shape."""
    return AgentResponse(response_text=extract_text(response), response_metadata=metadata)


async def collect_stream(chunks: AsyncIterable[Any] | Iterable[Any]) -> str:
    """Collect either an async or synchronous response stream."""
    if hasattr(chunks, "__aiter__"):
        parts: list[str] = []
        async for chunk in chunks:  # type: ignore[union-attr]
            if chunk:
                parts.append(str(chunk))
        return "".join(parts)

    return "".join(str(chunk) for chunk in chunks if chunk)
