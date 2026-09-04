from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/orchestration"
CANONICAL = ORCH / "agentic_ai_system.py"
RUNTIME = ORCH / "agentic_ai_system_runtime.py"
UPGRADED = ORCH / "agentic_ai_system_upgraded.py"
INTEGRATED = ORCH / "integrated_agent_system.py"


def test_canonical_surface_keeps_public_wrapper():
    tree = ast.parse(CANONICAL.read_text(encoding="utf-8"))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    agent = next(node for node in classes if node.name == "AsyncAgenticAiSystem")
    assert "IntegratedAsyncAgenticAiSystem" in [ast.unparse(base) for base in agent.bases]
    source = CANONICAL.read_text(encoding="utf-8")
    assert "async def upload_and_index_files(self, uploaded_files)" in source


def test_runtime_implementation_has_stable_internal_owner():
    assert RUNTIME.is_file()
    source = RUNTIME.read_text(encoding="utf-8")
    assert "class AsyncAgenticAiSystem" in source
    assert "from backend.orchestration.agentic_ai_system_runtime" not in source


def test_upgraded_module_is_compatibility_only():
    source = UPGRADED.read_text(encoding="utf-8")
    assert "from .agentic_ai_system_runtime import AsyncAgenticAiSystem, logger" in source
    assert "class AsyncAgenticAiSystem" not in source


def test_integrated_runtime_uses_internal_runtime_owner():
    source = INTEGRATED.read_text(encoding="utf-8")
    assert "from backend.orchestration.agentic_ai_system_runtime import AsyncAgenticAiSystem, logger" in source
    assert "agentic_ai_system_upgraded" not in source
