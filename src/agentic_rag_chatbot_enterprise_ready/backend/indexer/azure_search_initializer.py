"""Compatibility entry point for the canonical Azure Search initializer.

The maintained implementation lives in ``index_engine``. This historical
module preserves the older import path without retaining a second provider
implementation.
"""
from .index_engine import close_index, initialize_index

__all__ = ["initialize_index", "close_index"]
