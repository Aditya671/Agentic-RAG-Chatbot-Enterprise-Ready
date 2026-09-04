from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/user_uploaded_file_indexer.py"
PUBLIC_SURFACE = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/user_uploaded_file_indexer.py"
RETIRED = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/user_uploaded_file_indexer_upgraded.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_canonical_upload_indexer_defines_runtime_class() -> None:
    tree = ast.parse(CANONICAL.read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "UserUploadedFileIndexer"
        for node in tree.body
    )


def test_obsolete_upload_indexer_implementation_is_absent() -> None:
    assert not RETIRED.exists()


def test_public_upload_indexer_surface_points_to_indexer_package() -> None:
    text = PUBLIC_SURFACE.read_text(encoding="utf-8")
    assert "indexer.user_uploaded_file_indexer" in text
    assert "class UserUploadedFileIndexer" not in text
    assert "user_uploaded_file_indexer_upgraded" not in text
    assert not any(name.startswith("azure.") for name in _imports(PUBLIC_SURFACE))
