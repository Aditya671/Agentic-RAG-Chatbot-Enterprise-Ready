from __future__ import annotations

import sys
import types

import pytest

from backend.orchestration.tool_factory import build_function_tool, build_retriever_tool


def _install_fake_llama_tools(monkeypatch):
    module = types.ModuleType("llama_index.core.tools")

    class FunctionTool:
        @classmethod
        def from_defaults(cls, *, fn, name, description):
            return {"kind": "function", "fn": fn, "name": name, "description": description}

    class ToolMetadata:
        def __init__(self, *, name, description):
            self.name = name
            self.description = description

    class RetrieverTool:
        def __init__(self, *, retriever, metadata):
            self.retriever = retriever
            self.metadata = metadata

    module.FunctionTool = FunctionTool
    module.ToolMetadata = ToolMetadata
    module.RetrieverTool = RetrieverTool
    monkeypatch.setitem(sys.modules, "llama_index.core.tools", module)


def test_function_tool_factory_validates_and_delegates(monkeypatch):
    _install_fake_llama_tools(monkeypatch)
    fn = lambda value: value
    tool = build_function_tool(fn, "echo", "Echo input")

    assert tool["fn"] is fn
    assert tool["name"] == "echo"


def test_function_tool_factory_rejects_non_callable():
    with pytest.raises(TypeError, match="must be callable"):
        build_function_tool(None, "bad", "Invalid")


def test_retriever_tool_factory_validates_and_delegates(monkeypatch):
    _install_fake_llama_tools(monkeypatch)
    retriever = object()
    tool = build_retriever_tool(retriever, "search", "Search documents")

    assert tool.retriever is retriever
    assert tool.metadata.name == "search"


def test_retriever_tool_factory_rejects_none(monkeypatch):
    _install_fake_llama_tools(monkeypatch)
    with pytest.raises(ValueError, match="cannot be None"):
        build_retriever_tool(None, "search", "Search documents")
