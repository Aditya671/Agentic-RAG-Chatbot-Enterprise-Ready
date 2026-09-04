from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_retrieval_setting_matches_runtime_minimum():
    text = (
        ROOT
        / "src/agentic_rag_chatbot_enterprise_ready/frontend/app.py"
    ).read_text(encoding="utf-8")

    assert 'source["set_model_top_k"] = max(1, min(30,' in text
    assert 'id="set_model_top_k"' in text
    assert "min=1" in text
