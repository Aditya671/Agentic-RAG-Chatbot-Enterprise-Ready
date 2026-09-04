"""Regression tests for imports that previously produced Pylance diagnostics."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "agentic_rag_chatbot_enterprise_ready"


def _imports(path: Path) -> list[ast.ImportFrom]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]


def test_llama_index_document_uses_public_core_import() -> None:
    paths = [
        SRC / "backend" / "indexer" / "llama_indexer.py",
        SRC / "backend" / "indexer" / "pdf_indexer.py",
        SRC / "backend" / "process_doc" / "orchestrator" / "hierarchical_indexer.py",
    ]
    for path in paths:
        imports = _imports(path)
        document_imports = [
            node
            for node in imports
            if node.module == "llama_index.core"
            and any(alias.name == "Document" for alias in node.names)
        ]
        assert document_imports, f"{path} must import Document from llama_index.core"


def test_azure_ad_provider_does_not_require_nonexistent_userprincipalname_claim() -> None:
    source = (SRC / "auth" / "azure_ad_auth_provider.py").read_text(encoding="utf-8")
    assert 'identifier=azure_user["userPrincipalName"]' not in source
    assert 'identifier=identifier' in source
