"""Command-line entry point for the Agentic RAG application."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parent.parent
FRONTEND = PACKAGE_ROOT / "frontend" / "app.py"


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    paths = [str(PACKAGE_ROOT), str(PACKAGE_ROOT.parent)]
    existing = env.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def _run_frontend() -> int:
    if not FRONTEND.exists():
        raise FileNotFoundError(f"Chainlit frontend not found: {FRONTEND}")
    return subprocess.call(
        [sys.executable, "-m", "chainlit", "run", str(FRONTEND)],
        cwd=REPOSITORY_ROOT,
        env=_environment(),
    )


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="agentic-rag",
        description="Enterprise-ready Azure-native Agentic RAG Chatbot",
    )
    parser.add_argument("--frontend", action="store_true", help="Run the Chainlit frontend")
    parser.add_argument("--check", action="store_true", help="Run deterministic startup checks")
    args = parser.parse_args()

    if args.check:
        from agentic_rag_chatbot_enterprise_ready.backend.runtime import run_startup_checks

        checks = run_startup_checks()
        for name, ok, detail in checks:
            print(f"{'OK' if ok else 'FAIL'}  {name}: {detail}")
        raise SystemExit(0 if all(ok for _, ok, _ in checks) else 1)

    if args.frontend:
        raise SystemExit(_run_frontend())

    parser.print_help()


if __name__ == "__main__":
    cli()
