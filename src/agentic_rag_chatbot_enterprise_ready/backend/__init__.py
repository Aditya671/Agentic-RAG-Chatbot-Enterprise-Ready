"""Backward-compatible import surface for the modular backend package.

The original application imported modules from ``backend.*``.  Keeping that
namespace stable lets the business logic evolve without forcing a flag-day
rewrite of every integration and UI module.
"""
from .orchestration.agentic_ai_system import AsyncAgenticAiSystem

__all__ = ["AsyncAgenticAiSystem"]
