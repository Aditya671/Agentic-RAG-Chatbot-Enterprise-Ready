from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/llm_loader.py"
UPGRADED = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/llm_loader_upgraded.py"


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


def test_upgraded_loader_is_compatibility_only() -> None:
    text = UPGRADED.read_text(encoding="utf-8")
    assert "from .llm_loader import *" in text
    assert "def load_llm(" not in text
    assert "def load_embed(" not in text
    assert not any(name.startswith("azure.") for name in _imports(UPGRADED))
