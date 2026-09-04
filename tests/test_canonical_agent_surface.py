from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path("src/agentic_rag_chatbot_enterprise_ready/backend/orchestration")
CANONICAL = ROOT / "agentic_ai_system.py"


def test_canonical_agent_surface_inherits_converged_runtime():
    tree = ast.parse(CANONICAL.read_text())
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]

    agent = next(node for node in classes if node.name == "AsyncAgenticAiSystem")
    bases = [ast.unparse(base) for base in agent.bases]

    assert "IntegratedAsyncAgenticAiSystem" in bases
    assert "_ModernAsyncAgenticAiSystem" not in CANONICAL.read_text()


def test_legacy_upload_contract_remains_on_canonical_surface():
    source = CANONICAL.read_text()
    assert "async def upload_and_index_files(self, uploaded_files)" in source
    assert "await self.upload_and_index_files_async(payload)" in source
