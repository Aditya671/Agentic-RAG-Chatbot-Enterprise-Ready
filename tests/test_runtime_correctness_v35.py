from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_35_provider_boundary_documents_explicit_input_validation():
    text = (
        ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/provider_boundaries.py"
    ).read_text(encoding="utf-8")

    assert "if not isinstance(query_mode, str) or not query_mode.strip():" in text
    assert 'raise ValueError("query_mode must be a non-empty string")' in text
