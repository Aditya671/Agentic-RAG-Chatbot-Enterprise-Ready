"""Canonical Agentic RAG runtime.

The upgraded implementation is now the single source of truth.  The original
module path is retained so existing callers do not need a flag-day migration.
"""
from .agentic_ai_system_upgraded import AsyncAgenticAiSystem

__all__ = ["AsyncAgenticAiSystem"]
