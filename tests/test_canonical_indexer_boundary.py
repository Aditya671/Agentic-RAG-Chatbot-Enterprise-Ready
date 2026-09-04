"""Tests for canonical ingestion and Azure Search index boundaries."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEXER = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer.py"
SEARCH = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/index_engine.py"
SEARCH_COMPAT = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/index_engine_upgraded.py"
INDEXER_COMPAT = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer_upgraded.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_document_indexer_is_canonical() -> None:
    text = INDEXER.read_text(encoding="utf-8")
    assert "llama_indexer_upgraded" not in text
    assert "nest_asyncio" not in _imports(INDEXER)


def test_legacy_document_indexer_is_compatibility_only() -> None:
    text = INDEXER_COMPAT.read_text(encoding="utf-8")
    assert "from .llama_indexer import" in text or "from .llama_indexer" in text


def test_azure_search_initializer_is_canonical() -> None:
    text = SEARCH.read_text(encoding="utf-8")
    imports = _imports(SEARCH)
    assert "initialize_index" in text
    assert "azure.search.documents" in imports
    assert "nest_asyncio" not in imports
    assert "DefaultAzureCredential" not in text
    assert "GPTVectorStoreIndex" not in text
    assert "ServiceContext" not in text


def test_upgraded_search_initializer_is_compatibility_only() -> None:
    text = SEARCH_COMPAT.read_text(encoding="utf-8")
    assert "from .index_engine import" in text
    assert "AzureAISearchVectorStore" not in text
    assert "DefaultAzureCredential" not in text


def test_canonical_document_indexer_defines_expected_supported_formats() -> None:
    canonical = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer.py"
    tree = ast.parse(canonical.read_text(encoding="utf-8"))
    names = {
        node.targets[0].id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    assert "SUPPORTED_EXTENSIONS" in names


def test_canonical_search_engine_exposes_lifecycle_api() -> None:
    text = SEARCH.read_text(encoding="utf-8")
    assert "def initialize_index(" in text
    assert "async def close_index(" in text
    assert "IndexManagement.VALIDATE_INDEX" in text
