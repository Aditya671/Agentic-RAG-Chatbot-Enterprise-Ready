"""Removed code-execution compatibility surface.

The application intentionally does not provide arbitrary code execution or
remote sandbox access. This module remains only so historical imports fail
explicitly rather than silently restoring an execution capability.
"""
from __future__ import annotations


class CodeInterpreterSandbox:
    """Compatibility placeholder for the removed code-execution feature."""

    def __init__(self, *args, **kwargs) -> None:
        raise RuntimeError(
            "Code execution is not supported by this application. "
            "The sandbox capability has been removed."
        )
