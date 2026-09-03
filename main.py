"""Repository CLI entry point."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT / "src" / "agentic_rag_chatbot_enterprise_ready"
if PACKAGE_ROOT.exists():
    sys.path.insert(0, str(PACKAGE_ROOT))


def _run_chainlit() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(PACKAGE_ROOT), str(ROOT / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return subprocess.call(
        [sys.executable, "-m", "chainlit", "run", str(ROOT / "frontend" / "app.py")],
        cwd=ROOT,
        env=env,
    )


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="agentic-rag",
        description="Enterprise-ready Azure-native Agentic RAG Chatbot",
    )
    parser.add_argument("--frontend", action="store_true", help="Run the Chainlit frontend")
    parser.add_argument("--check", action="store_true", help="Validate the local runtime contract")
    args = parser.parse_args()

    if args.check:
        from backend.runtime import run_startup_checks

        checks = run_startup_checks()
        for name, ok, detail in checks:
            print(f"{'OK' if ok else 'FAIL'}  {name}: {detail}")
        raise SystemExit(0 if all(ok for _, ok, _ in checks) else 1)

    if args.frontend:
        raise SystemExit(_run_chainlit())

    parser.print_help()


if __name__ == "__main__":
    cli()
