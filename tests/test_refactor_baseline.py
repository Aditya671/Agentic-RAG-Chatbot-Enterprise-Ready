from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "agentic_rag_chatbot_enterprise_ready"


def test_python_sources_compile() -> None:
    files = list((ROOT / "src").rglob("*.py")) + [ROOT / "main.py"]
    assert files
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_no_mutable_constructor_defaults_in_agent() -> None:
    path = PACKAGE_ROOT / "backend" / "orchestration" / "agentic_ai_system.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__init__":
            for default in node.args.defaults:
                assert not isinstance(default, (ast.List, ast.Dict, ast.Set)), f"mutable default in {path}"


def test_required_runtime_files_exist() -> None:
    for relative in (
        "pyproject.toml",
        "main.py",
        "src/agentic_rag_chatbot_enterprise_ready/frontend/app.py",
        "src/agentic_rag_chatbot_enterprise_ready/backend/runtime.py",
    ):
        assert (ROOT / relative).exists(), relative
