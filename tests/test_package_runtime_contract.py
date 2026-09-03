"""Tests for package/runtime contracts that do not require Azure resources."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path


def test_package_import_registers_backend_compatibility_alias() -> None:
    package = importlib.import_module("agentic_rag_chatbot_enterprise_ready")
    backend = importlib.import_module("backend")

    assert backend is package.backend
    assert importlib.import_module("backend.config")


def test_canonical_agent_upload_adapter_is_async() -> None:
    source = Path(
        "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/agentic_ai_system.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    methods = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name == "upload_and_index_files"
    ]
    assert len(methods) == 1
    assert isinstance(methods[0], ast.AsyncFunctionDef)
