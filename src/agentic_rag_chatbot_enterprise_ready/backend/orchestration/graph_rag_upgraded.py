"""Compatibility import for the canonical GraphRAG runtime.

The maintained implementation lives in ``graph_rag``. This module remains
only so older integrations importing the historical upgraded path continue to
resolve without maintaining a second GraphRAG implementation.
"""
from .graph_rag import GraphRAGConfigurationError, GraphRAGError, GraphRAGSystem

__all__ = ["GraphRAGConfigurationError", "GraphRAGError", "GraphRAGSystem"]
