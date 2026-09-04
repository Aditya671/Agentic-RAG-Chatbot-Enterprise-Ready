"""Compatibility adapter for the canonical document ingestion pipeline.

PDF ingestion is owned by ``llama_indexer``. This historical module keeps the
PDF-specific import path available without maintaining a second Azure Search
or LlamaIndex implementation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from llama_index.core.schema import Document

from .llama_indexer import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBED_BATCH_SIZE,
    SUPPORTED_EXTENSIONS,
    build_doc_metadata_for_file,
    chunk_text_simple,
    compute_checksum_file,
    create_documents_from_text,
    extract_text_from_pdf as _extract_text_from_pdf,
    index_file,
    init_embedding_and_vectorstore,
    upsert_documents_to_index,
)


def compute_checksum(file_path: str) -> str:
    """Preserve the historical checksum helper."""
    return compute_checksum_file(file_path)


def extract_text_from_pdf(file_path: str) -> Tuple[str, int]:
    """Delegate PDF extraction to the canonical ingestion implementation."""
    return _extract_text_from_pdf(file_path)


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Tuple[str, int, int]]:
    """Preserve the historical chunking helper through the canonical pipeline."""
    return chunk_text_simple(text, chunk_size=chunk_size, overlap=overlap)


def build_metadata_for_doc(file_path: str, checksum: str) -> Dict[str, Any]:
    """Build PDF metadata through the canonical ingestion metadata contract."""
    return build_doc_metadata_for_file(file_path, checksum)


def create_documents_from_pdf(
    file_path: str,
) -> Tuple[List[Document], Dict[str, Any]]:
    """Create PDF documents using the canonical chunk/document builder."""
    checksum = compute_checksum(file_path)
    text, page_count = extract_text_from_pdf(file_path)
    metadata = build_metadata_for_doc(file_path, checksum)
    metadata["page_count"] = page_count
    return create_documents_from_text(text, metadata), metadata


def index_pdf(
    file_path: str,
    force_reindex: bool = False,
    vector_store: Any = None,
    service_context: Any = None,
) -> Dict[str, Any]:
    """Index a PDF through the canonical multi-format ingestion pipeline."""
    return index_file(
        file_path,
        force_reindex=force_reindex,
        vector_store=vector_store,
        service_context=service_context,
    )


__all__ = [
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "EMBED_BATCH_SIZE",
    "SUPPORTED_EXTENSIONS",
    "compute_checksum",
    "extract_text_from_pdf",
    "chunk_text",
    "build_metadata_for_doc",
    "create_documents_from_pdf",
    "init_embedding_and_vectorstore",
    "upsert_documents_to_index",
    "index_pdf",
]
