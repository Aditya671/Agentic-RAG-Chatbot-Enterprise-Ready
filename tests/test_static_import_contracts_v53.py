"""Regression tests for imports corrected in the static/runtime audit."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "agentic_rag_chatbot_enterprise_ready"


def _imports(path: Path) -> list[ast.ImportFrom]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]


def test_pdf_and_hierarchy_use_public_document_import() -> None:
    paths = [
        SRC / "backend" / "indexer" / "pdf_indexer.py",
        SRC / "backend" / "process_doc" / "orchestrator" / "hierarchical_indexer.py",
    ]
    for path in paths:
        imports = _imports(path)
        assert any(
            node.module == "llama_index.core"
            and any(alias.name == "Document" for alias in node.names)
            for node in imports
        ), f"{path} must import Document from llama_index.core"


def test_azure_ad_provider_uses_resolved_identifier_claim() -> None:
    source = (SRC / "auth" / "azure_ad_auth_provider.py").read_text(encoding="utf-8")
    assert 'identifier=azure_user["userPrincipalName"]' not in source
    assert "identifier=identifier" in source
