"""Provider-neutral construction of LlamaIndex agent tools.

The canonical runtime should not reach into name-mangled implementation
helpers merely to construct tools. This module owns the small provider-facing
translation required by the current LlamaIndex agent API.
"""
from __future__ import annotations

from typing import Any


def build_function_tool(fn: Any, name: str, description: str) -> Any:
    """Create a callable agent tool with a stable application contract."""
    if not callable(fn):
        raise TypeError(f"Tool '{name}' function must be callable.")
    from llama_index.core.tools import FunctionTool

    return FunctionTool.from_defaults(fn=fn, name=name, description=description)


def build_retriever_tool(retriever: Any, name: str, description: str) -> Any:
    """Create a retriever tool at the provider edge."""
    if retriever is None:
        raise ValueError(f"Retriever for tool '{name}' cannot be None.")
    from llama_index.core.tools import RetrieverTool, ToolMetadata

    return RetrieverTool(
        retriever=retriever,
        metadata=ToolMetadata(name=name, description=description),
    )
