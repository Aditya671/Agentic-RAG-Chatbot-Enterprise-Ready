from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "agentic_rag_chatbot_enterprise_ready"
ORCHESTRATION = PACKAGE / "backend" / "orchestration"


def test_maintained_agent_builder_does_not_register_code_execution():
    text = (ORCHESTRATION / "agent_builder.py").read_text(encoding="utf-8")
    assert "code_interpreter_tool" not in text
    assert "run_python" not in text
    assert "AGENTIC_AI_CODEX_PROMPT" not in text


def test_compatibility_component_never_constructs_a_sandbox():
    text = (ORCHESTRATION / "component_runtime.py").read_text(encoding="utf-8")
    assert "return initialize()" not in text
    assert "Code execution was requested but is no longer supported" in text


def test_compatibility_code_interpreter_has_no_provider_dependency():
    text = (ORCHESTRATION / "code_interpreter.py").read_text(encoding="utf-8")
    assert "e2b" not in text.casefold()
    assert "run_python" not in text
    assert "raise RuntimeError" in text


def test_retirement_boundary_documented():
    path = ROOT / "docs" / "code-execution-retirement.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "does not support arbitrary Python execution" in text
    assert "generated-code execution" in text
