"""Canonical LLM and embedding loader.

The upgraded implementation is the source of truth while this module path
remains stable for existing callers.
"""
from .llm_loader_upgraded import *  # noqa: F401,F403
