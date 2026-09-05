"""Repository-level compatibility entry point."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def main() -> None:
    """Run the packaged CLI while preserving checkout-based execution."""
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from agentic_rag_chatbot_enterprise_ready.cli import cli

    cli()


if __name__ == "__main__":
    main()
