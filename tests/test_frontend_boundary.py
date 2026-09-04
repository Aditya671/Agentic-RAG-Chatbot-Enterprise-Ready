"""Regression guards for the canonical Chainlit application surface."""
from pathlib import Path


APP_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "agentic_rag_chatbot_enterprise_ready"
    / "frontend"
    / "app.py"
)
UPGRADED_PATH = APP_PATH.with_name("app_upgraded.py")


def test_canonical_frontend_exists():
    assert APP_PATH.is_file()


def test_frontend_does_not_retain_upgraded_implementation():
    assert not UPGRADED_PATH.exists()
