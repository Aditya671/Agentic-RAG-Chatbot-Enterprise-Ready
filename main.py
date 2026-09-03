"""Repository-level compatibility entry point.

The packaged CLI is the authoritative implementation. This module remains so
existing ``python main.py`` workflows continue to work from a checkout.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_rag_chatbot_enterprise_ready.cli import cli


if __name__ == "__main__":
    cli()
