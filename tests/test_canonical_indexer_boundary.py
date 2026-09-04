"""Tests for canonical ingestion and Azure Search index boundaries."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEXER = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer.py"
SEARCH = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/index_engine.py"
RETIRED_INDEXER = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer_upgraded.py"
RETIRED_SEARCH = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/index_engine_upgraded.py"
AZURE_COMPAT = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/azure_search_initializer.py"
AZURE_UPGRADED = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/azure_search_initializer_upgraded.py"


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


def test_retired_document_indexer_implementation_is_absent() -> None:
    assert not RETIRED_INDEXER.exists()


def test_azure_search_index_engine_is_canonical() -> None:
    text = SEARCH.read_text(encoding="utf-8")
    imports = _imports(SEARCH)
    assert "initialize_index" in text
    assert "azure.search.documents.aio" in imports
    assert "azure.search.documents.indexes" in imports
    assert "nest_asyncio" not in imports
    assert "DefaultAzureCredential" not in text
    assert "GPTVectorStoreIndex" not in text
    assert "ServiceContext" not in text


def test_retired_index_engine_implementation_is_absent() -> None:
    assert not RETIRED_SEARCH.exists()


def test_historical_azure_initializer_is_compatibility_only() -> None:
    text = AZURE_COMPAT.read_text(encoding="utf-8")
    assert "from .index_engine import" in text
    assert "azure_search_initializer_upgraded" not in text
    assert "AzureAISearchVectorStore" not in text
    assert "DefaultAzureCredential" not in text


def test_obsolete_azure_initializer_implementation_is_removed() -> None:
    assert not AZURE_UPGRADED.exists()


def test_canonical_document_indexer_defines_expected_supported_formats() -> None:
    tree = ast.parse(INDEXER.read_text(encoding="utf-8"))
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
