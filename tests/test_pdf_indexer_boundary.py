from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/pdf_indexer.py"
CANONICAL = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer.py"
UPGRADED = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/pdf_indexer_upgraded.py"


def test_pdf_indexer_is_only_a_compatibility_adapter() -> None:
    source = PDF.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_names = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert function_names == {
        "compute_checksum",
        "extract_text_from_pdf",
        "chunk_text",
        "build_metadata_for_doc",
        "create_documents_from_pdf",
        "index_pdf",
    }
    assert "AzureAISearchVectorStore" not in source
    assert "ServiceContext" not in source
    assert "GPTVectorStoreIndex" not in source


def test_pdf_indexer_delegates_to_canonical_indexer() -> None:
    source = PDF.read_text(encoding="utf-8")
    canonical = CANONICAL.read_text(encoding="utf-8")

    assert "from .llama_indexer import" in source
    assert "return index_file(" in source
    assert "def index_file(" in canonical
    assert "VectorStoreIndex(" in canonical


def test_duplicate_pdf_implementation_is_removed() -> None:
    assert not UPGRADED.exists()
