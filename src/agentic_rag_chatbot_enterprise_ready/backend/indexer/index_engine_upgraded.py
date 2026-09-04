"""Compatibility import for the canonical Azure Search index engine.

The maintained implementation lives in ``index_engine``. This historical
module is intentionally implementation-free so existing imports continue to
work without preserving a second provider integration.
"""
from .index_engine import EmbeddingModel, close_index, initialize_index

__all__ = ["EmbeddingModel", "initialize_index", "close_index"]
