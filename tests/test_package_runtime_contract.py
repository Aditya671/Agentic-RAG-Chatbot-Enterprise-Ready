"""Tests for package/runtime contracts that do not require Azure resources."""

from __future__ import annotations

import importlib


def test_package_import_registers_backend_compatibility_alias() -> None:
    package = importlib.import_module("agentic_rag_chatbot_enterprise_ready")
    backend = importlib.import_module("backend")

    assert backend is package.backend
    assert importlib.import_module("backend.config")


def test_canonical_agent_upload_adapter_is_async() -> None:
    module = importlib.import_module(
        "agentic_rag_chatbot_enterprise_ready.backend.orchestration.agentic_ai_system"
    )
    method = module.AsyncAgenticAiSystem.upload_and_index_files

    assert callable(method)
    assert getattr(method, "__code__").co_flags & 0x80  # inspect.CO_COROUTINE
