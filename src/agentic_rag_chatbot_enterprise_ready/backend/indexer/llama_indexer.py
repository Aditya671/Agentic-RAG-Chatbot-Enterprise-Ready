"""Compatibility entry point for the canonical document indexer.

The production ingestion implementation lives in ``llama_indexer_upgraded``.
This module deliberately contains no legacy LlamaIndex APIs, Azure credentials,
or event-loop patching.
"""

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

__all__ = [
    "CHUNK_OVERLAP", "CHUNK_SIZE", "EMBED_BATCH_SIZE", "INDEX_VERSION",
    "SUPPORTED_EXTENSIONS", "IndexRuntime", "build_doc_metadata_for_file",
    "chunk_text_simple", "compute_checksum_bytes", "compute_checksum_file",
    "create_documents_from_text", "extract_text_from_csv",
    "extract_text_from_dataframe", "extract_text_from_docx", "extract_text_from_pdf",
    "extract_text_from_txt", "index_dataframe", "index_file", "index_path",
    "init_embedding_and_vectorstore", "make_doc_id", "now_iso", "semantic_search",
]
