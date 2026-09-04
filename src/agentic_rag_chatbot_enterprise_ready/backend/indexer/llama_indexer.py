"""Canonical document-ingestion public surface.

The enhanced ingestion implementation remains in the historical upgraded
module while this stable public module owns the application-facing exports.
The reconciliation adds the missing document-upsert helper required by the
PDF compatibility surface without duplicating ingestion logic.
"""

from __future__ import annotations

from typing import Any, Sequence

from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.schema import Document

from .llama_indexer_upgraded import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBED_BATCH_SIZE,
    INDEX_VERSION,
    SUPPORTED_EXTENSIONS,
    IndexRuntime,
    build_doc_metadata_for_file,
    chunk_text_simple,
    compute_checksum_bytes,
    compute_checksum_file,
    create_documents_from_text,
    extract_text_from_csv,
    extract_text_from_dataframe,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt,
    index_dataframe,
    index_file,
    index_path,
    init_embedding_and_vectorstore,
    make_doc_id,
    now_iso,
    semantic_search,
)


def upsert_documents_to_index(
    documents: Sequence[Document],
    vector_store: Any,
    *,
    embed_model: Any = None,
    insert_batch_size: int = EMBED_BATCH_SIZE,
) -> None:
    """Insert document nodes into an existing vector store.

    This is the historical PDF helper contract. It now uses the same current
    LlamaIndex storage boundary as the enhanced ingestion implementation.
    """
    if isinstance(documents, (str, bytes, bytearray)) or not isinstance(documents, Sequence):
        raise TypeError("documents must be a sequence of LlamaIndex Document objects.")
    if not documents:
        return
    if vector_store is None:
        raise ValueError("vector_store is required.")
    if isinstance(insert_batch_size, bool) or not isinstance(insert_batch_size, int) or insert_batch_size < 1:
        raise ValueError("insert_batch_size must be a positive integer.")
    for document in documents:
        if not isinstance(document, Document):
            raise TypeError("documents must contain only LlamaIndex Document objects.")

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(
        nodes=list(documents),
        storage_context=storage_context,
        embed_model=embed_model or Settings.embed_model,
        insert_batch_size=insert_batch_size,
        show_progress=False,
    )


__all__ = [
    "CHUNK_OVERLAP", "CHUNK_SIZE", "EMBED_BATCH_SIZE", "INDEX_VERSION",
    "SUPPORTED_EXTENSIONS", "IndexRuntime", "build_doc_metadata_for_file",
    "chunk_text_simple", "compute_checksum_bytes", "compute_checksum_file",
    "create_documents_from_text", "extract_text_from_csv",
    "extract_text_from_dataframe", "extract_text_from_docx", "extract_text_from_pdf",
    "extract_text_from_txt", "index_dataframe", "index_file", "index_path",
    "init_embedding_and_vectorstore", "make_doc_id", "now_iso", "semantic_search",
    "upsert_documents_to_index",
]
