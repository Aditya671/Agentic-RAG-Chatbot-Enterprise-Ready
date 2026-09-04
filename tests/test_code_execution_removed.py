from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_builder_has_no_code_execution_tool():
    text = (ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/agent_builder.py").read_text(encoding="utf-8")
    assert "code_interpreter_tool" not in text
    assert "run_python" not in text
    assert "AGENTIC_AI_CODEX_PROMPT" not in text


def test_runtime_component_cannot_construct_code_execution():
    text = (ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/component_runtime.py").read_text(encoding="utf-8")
    assert "return initialize()" not in text
    assert "Code execution was requested but is no longer supported" in text


def test_legacy_code_interpreter_module_is_explicitly_non_executable():
    text = (ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration/code_interpreter.py").read_text(encoding="utf-8")
    assert "from e2b" not in text
    assert "e2b_code_interpreter" not in text
    assert "raise RuntimeError" in text
