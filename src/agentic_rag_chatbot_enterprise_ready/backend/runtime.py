"""Deterministic startup diagnostics; cloud resources are never contacted here."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path


REQUIRED_MODULES = (
    "backend.config",
    "backend.ai_models",
    "backend.azure_credential_manager",
    "backend.llm_loader",
    "backend.orchestration.agentic_ai_system",
    "backend.retrievers.azure_blob_file_retriever",
    "backend.process_doc.orchestrator.pipeline",
)


def run_startup_checks() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("python", sys.version_info >= (3, 12), sys.version.split()[0]))
    root = Path(__file__).resolve().parents[3]
    checks.append(("package-root", root.exists(), str(root)))
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            checks.append((f"import:{module_name}", False, f"{type(exc).__name__}: {exc}"))
        else:
            checks.append((f"import:{module_name}", True, "importable"))
    return checks
