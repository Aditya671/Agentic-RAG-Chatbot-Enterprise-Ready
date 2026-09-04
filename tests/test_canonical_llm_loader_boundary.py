from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/llm_loader.py"
RETIRED = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/llm_loader_upgraded.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_canonical_loader_contains_the_implementation() -> None:
    text = CANONICAL.read_text(encoding="utf-8")
    assert "def load_llm(" in text
    assert "def load_embed(" in text
    assert "class LLMConfigurationError" in text


def test_obsolete_upgraded_loader_is_absent() -> None:
    assert not RETIRED.exists()


def test_canonical_loader_does_not_require_an_upgraded_runtime_module() -> None:
    imports = _imports(CANONICAL)
    assert "llm_loader_upgraded" not in imports
