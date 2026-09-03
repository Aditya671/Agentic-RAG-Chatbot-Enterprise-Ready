"""Compatibility entry point for the canonical Azure Search initializer.

The production implementation lives in ``index_engine_upgraded``.  Keeping
this module as a thin re-export prevents the legacy implementation from being
selected accidentally while preserving existing import paths.
"""

from .index_engine_upgraded import initialize_index

__all__ = ["initialize_index"]
