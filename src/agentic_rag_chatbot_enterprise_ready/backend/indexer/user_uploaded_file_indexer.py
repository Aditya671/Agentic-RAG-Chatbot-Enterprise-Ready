"""Canonical entry point for user-uploaded file indexing.

The maintained implementation lives in ``user_uploaded_file_indexer_upgraded``.
This compatibility module preserves the historical import path without
retaining a second implementation of the indexing lifecycle.
"""

from .user_uploaded_file_indexer_upgraded import UserUploadedFileIndexer

__all__ = ["UserUploadedFileIndexer"]
