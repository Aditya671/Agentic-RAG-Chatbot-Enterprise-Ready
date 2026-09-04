"""Compatibility entry point for the canonical agent runtime.

The maintained implementation lives in ``agentic_ai_system_runtime``. This
historical module remains importable for callers that still reference the
``*_upgraded`` name, but it contains no independent runtime implementation.
"""
from .agentic_ai_system_runtime import AsyncAgenticAiSystem, logger

__all__ = ["AsyncAgenticAiSystem", "logger"]
