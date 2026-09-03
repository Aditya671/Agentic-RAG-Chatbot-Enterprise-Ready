"""Tests for the canonical ingestion/indexing boundary."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEXER = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer.py"
SEARCH = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/index_engine.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_legacy_indexer_is_only_a_compatibility_boundary() -> None:
    text = INDEXER.read_text(encoding="utf-8")
    imports = _imports(INDEXER)

    assert "llama_indexer_upgraded" in text
    assert not any(name == "nest_asyncio" for name in imports)
    assert not any(name.startswith("llama_index.core.schema") for name in imports)
    assert not any(name.startswith("llama_index.core") for name in imports)
    assert not any(name.startswith("azure.") for name in imports)


def test_legacy_search_initializer_is_only_a_compatibility_boundary() -> None:
    text = SEARCH.read_text(encoding="utf-8")
    imports = _imports(SEARCH)

    assert "index_engine_upgraded" in text
    assert "nest_asyncio" not in imports
    assert not any(name.startswith("azure.") for name in imports)


def test_canonical_indexer_defines_expected_supported_formats() -> None:
    canonical = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer_upgraded.py"
    tree = ast.parse(canonical.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "SUPPORTED_EXTENSIONS"
    }
    assert "SUPPORTED_EXTENSIONS" in assignments
