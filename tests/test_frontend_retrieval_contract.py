from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src/agentic_rag_chatbot_enterprise_ready/frontend/app.py"


def test_frontend_retrieval_normalization_declares_runtime_compatible_lower_bound():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    source = APP.read_text(encoding="utf-8")
    assert "set_model_top_k" in source
    assert "max(1" in source
    assert "min=1" in source
    assert tree.body
