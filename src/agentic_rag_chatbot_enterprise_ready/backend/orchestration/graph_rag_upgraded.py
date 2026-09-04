"""Compatibility import for the canonical GraphRAG runtime.

The maintained implementation lives in ``graph_rag``. This historical module
contains no independent implementation and exists only for import stability.
"""
from .graph_rag import GraphRAGConfigurationError, GraphRAGError, GraphRAGSystem

__all__ = ["GraphRAGConfigurationError", "GraphRAGError", "GraphRAGSystem"]
