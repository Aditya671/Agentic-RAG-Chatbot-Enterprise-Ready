"""Enterprise-ready Agentic RAG Chatbot package.

The historical codebase uses ``backend.*`` imports internally.  The project
now has a real ``src`` package layout, so this module registers a lightweight
compatibility alias before backend submodules are imported.  This keeps the
existing module topology working without duplicating the backend package.
"""

from __future__ import annotations

import sys

from . import backend as _backend

sys.modules.setdefault("backend", _backend)

__all__ = []
