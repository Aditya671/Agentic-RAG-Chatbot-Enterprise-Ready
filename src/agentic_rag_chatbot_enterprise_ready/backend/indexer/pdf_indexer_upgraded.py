"""Production-oriented PDF indexing pipeline.

This module preserves the original public helpers while upgrading the
implementation to current LlamaIndex/Azure AI Search patterns.

The module deliberately remains PDF-specific. Shared ingestion architecture
will be consolidated only after the individual indexer files are upgraded.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import fitz
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.schema import Document
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.vector_stores.azureaisearch import (
    AzureAISearchVectorStore,
    IndexManagement,
)
from app_logger import setup_logger

logger, _ = setup_logger(name="pdf-indexer")

CHUNK_SIZE = int(os.getenv("PDF_INDEX_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("PDF_INDEX_CHUNK_OVERLAP", "200"))
EMBED_BATCH_SIZE = int(os.getenv("PDF_INDEX_EMBED_BATCH_SIZE", "16"))
INDEX_VERSION = os.getenv("PDF_INDEX_VERSION", "v2")
DEFAULT_METADATA_PATH = os.getenv(
    "PDF_INDEX_METADATA_PATH",
    ".pdf_index_metadata.json",
)
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "AZURE_OPENAI_EMBED_MODEL",
    "text-embedding-3-large",
)
DEFAULT_EMBEDDING_DIMENSION = int(
    os.getenv("AZURE_OPENAI_EMBED_DIMENSION", "3072")
)


def now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_checksum(file_path: str) -> str:
    """Compute SHA-256 using bounded-memory streaming reads."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_chunking(chunk_size: int, overlap: int) -> None:
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise ValueError("chunk_size must be an integer.")
    if isinstance(overlap, bool) or not isinstance(overlap, int):
        raise ValueError("overlap must be an integer.")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if overlap < 0:
        raise ValueError("overlap must be non-negative.")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")


def extract_text_from_pdf(file_path: str) -> Tuple[str, int]:
    """Extract PDF text while guaranteeing the document is closed."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path.suffix or '<none>'}")

    document = fitz.open(str(path))
    try:
        text_parts = [page.get_text("text") for page in document]
        return "\n".join(text_parts), len(document)
    finally:
        document.close()


def extract_pdf_pages(file_path: str) -> List[Tuple[int, str, int, int]]:
    """Return page number and character offsets for page-aware metadata.

    Page numbers are one-based for application-facing metadata. Offsets refer
    to the concatenated text returned by ``extract_text_from_pdf`` semantics.
    """
    document = fitz.open(file_path)
    try:
        pages: List[Tuple[int, str, int, int]] = []
        cursor = 0

        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text")
            start = cursor
            end = start + len(text)
            pages.append((page_number, text, start, end))
            cursor = end + 1  # account for the "\n" joining page texts

        return pages
    finally:
        document.close()


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Tuple[str, int, int]]:
    """Chunk text into deterministic overlapping character windows."""
    _validate_chunking(chunk_size, overlap)

    if not text:
        return []

    step = chunk_size - overlap
    chunks: List[Tuple[str, int, int]] = []

    for start in range(0, len(text), step):
        end = min(start + chunk_size, len(text))
        chunks.append((text[start:end], start, end))
        if end >= len(text):
            break

    return chunks


def _page_for_offset(
    pages: Sequence[Tuple[int, str, int, int]],
    offset: int,
) -> Optional[int]:
    for page_number, _, start, end in pages:
        if start <= offset < end:
            return page_number

    if pages and offset == pages[-1][3]:
        return pages[-1][0]

    return None


def _page_range_for_chunk(
    pages: Sequence[Tuple[int, str, int, int]],
    start: int,
    end: int,
) -> Tuple[Optional[int], Optional[int]]:
    if not pages:
        return None, None

    # Treat the end offset as exclusive.
    effective_end = max(start, end - 1)
    return _page_for_offset(pages, start), _page_for_offset(pages, effective_end)


def build_metadata_for_doc(
    file_path: str,
    checksum: str,
    *,
    page_count: Optional[int] = None,
) -> Dict[str, Any]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    stat = path.stat()

    metadata: Dict[str, Any] = {
        "doc_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve()))),
        "source_path": str(path.resolve()),
        "filename": path.name,
        "checksum": checksum,
        "uploaded_date": now_iso(),
        "last_modified": datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat().replace("+00:00", "Z"),
        "file_size": stat.st_size,
        "mime_type": "application/pdf",
        "index_version": INDEX_VERSION,
        "ingest_pipeline": "pdf-indexer-v2",
    }

    if page_count is not None:
        metadata["page_count"] = page_count

    return metadata


def create_documents_from_pdf(
    file_path: str,
) -> Tuple[List[Document], Dict[str, Any]]:
    """Extract, chunk, and create LlamaIndex documents with page metadata."""
    checksum = compute_checksum(file_path)
    pages = extract_pdf_pages(file_path)
    text = "\n".join(page_text for _, page_text, _, _ in pages)

    metadata = build_metadata_for_doc(
        file_path,
        checksum,
        page_count=len(pages),
    )

    documents: List[Document] = []

    for index, (chunk, start, end) in enumerate(
        chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    ):
        chunk_id = f"{metadata['doc_id']}::chunk::{index}"
        start_page, end_page = _page_range_for_chunk(pages, start, end)

        chunk_metadata = dict(metadata)
        chunk_metadata.update(
            {
                "chunk_id": chunk_id,
                "chunk_start_offset": start,
                "chunk_end_offset": end,
                "chunk_start_page": start_page,
                "chunk_end_page": end_page,
                "indexed_at": now_iso(),
            }
        )

        documents.append(
            Document(
                text=chunk,
                metadata=chunk_metadata,
                id_=chunk_id,
            )
        )

    return documents, metadata


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise ValueError(f"Required environment variable '{name}' is missing.")
    return value.strip()


def init_embedding_and_vectorstore():
    """Initialize current Azure OpenAI + Azure AI Search integrations.

    The third return value is retained as ``None`` for compatibility with
    callers that previously expected a LlamaIndex ServiceContext.
    """
    endpoint = _require_env("AZURE_OPENAI_ENDPOINT")
    api_version = _require_env("AZURE_OPENAI_API_VERSION")
    api_key = _require_env("AZURE_OPENAI_API_KEY")
    deployment = os.getenv(
        "AZURE_OPENAI_EMBED_DEPLOYMENT",
        DEFAULT_EMBEDDING_MODEL,
    )

    embedding = AzureOpenAIEmbedding(
        model=DEFAULT_EMBEDDING_MODEL,
        deployment_name=deployment,
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
        embed_batch_size=EMBED_BATCH_SIZE,
    )

    Settings.embed_model = embedding
    Settings.chunk_size = CHUNK_SIZE
    Settings.chunk_overlap = CHUNK_OVERLAP

    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not search_endpoint:
        service_name = _require_env("AZURE_SEARCH_SERVICE_NAME")
        search_endpoint = f"https://{service_name}.search.windows.net"

    search_key = _require_env("AZURE_SEARCH_API_KEY")
    index_name = _require_env("AZURE_SEARCH_INDEX_NAME")

    search_index_client = SearchIndexClient(
        endpoint=search_endpoint,
        credential=AzureKeyCredential(search_key),
    )

    vector_store = AzureAISearchVectorStore(
        search_or_index_client=search_index_client,
        index_name=index_name,
        index_management=IndexManagement.CREATE_IF_NOT_EXISTS,
        id_field_key="id",
        chunk_field_key="chunk",
        embedding_field_key="embedding",
        embedding_dimensionality=DEFAULT_EMBEDDING_DIMENSION,
        metadata_string_field_key="metadata",
        doc_id_field_key="doc_id",
        vector_algorithm_type=os.getenv(
            "AZURE_SEARCH_VECTOR_ALGORITHM",
            "exhaustiveKnn",
        ),
    )

    return embedding, vector_store, None


def _load_metadata(path: str) -> Dict[str, Any]:
    metadata_path = Path(path)
    if not metadata_path.exists():
        return {}

    try:
        with metadata_path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid PDF index metadata file: {metadata_path}") from exc

    if not isinstance(value, dict):
        raise ValueError("PDF index metadata must be a JSON object.")

    return value


def _save_metadata(path: str, metadata: Dict[str, Any]) -> None:
    metadata_path = Path(path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    temporary = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(metadata_path)


def _is_unchanged(
    metadata: Dict[str, Any],
    doc_id: str,
    checksum: str,
) -> bool:
    record = metadata.get(doc_id)
    return (
        isinstance(record, dict)
        and record.get("checksum") == checksum
        and record.get("index_version") == INDEX_VERSION
    )


def _delete_existing_document(vector_store: Any, doc_id: str) -> None:
    delete_method = getattr(vector_store, "delete", None)
    if not callable(delete_method):
        return

    try:
        delete_method(doc_id)
    except TypeError:
        try:
            delete_method(ref_doc_id=doc_id)
        except Exception:
            logger.warning(
                "Unable to remove existing PDF document %s before reindex.",
                doc_id,
                exc_info=True,
            )
    except Exception:
        logger.warning(
            "Existing PDF document cleanup failed for %s.",
            doc_id,
            exc_info=True,
        )


def upsert_documents_to_index(
    docs: List[Document],
    vector_store: Any,
    service_context: Any = None,
) -> None:
    """Insert PDF chunks into the current LlamaIndex vector store."""
    del service_context  # Compatibility-only argument.

    if not docs:
        logger.info("No PDF chunks to index.")
        return

    if Settings.embed_model is None:
        raise RuntimeError(
            "Settings.embed_model is not initialized. "
            "Call init_embedding_and_vectorstore() first."
        )

    logger.info("Upserting %d PDF chunks to vector store.", len(docs))

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(
        nodes=docs,
        storage_context=storage_context,
        embed_model=Settings.embed_model,
        insert_batch_size=EMBED_BATCH_SIZE,
        show_progress=False,
    )

    logger.info("PDF upsert complete.")


def index_pdf(
    file_path: str,
    force_reindex: bool = False,
    vector_store: Any = None,
    service_context: Any = None,
) -> Dict[str, Any]:
    """Index a PDF, skipping unchanged content unless forced."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path.suffix or '<none>'}")

    logger.info("Indexing PDF: %s", path)

    checksum = compute_checksum(str(path))
    metadata = build_metadata_for_doc(str(path), checksum)

    metadata_path = os.getenv(
        "PDF_INDEX_METADATA_PATH",
        DEFAULT_METADATA_PATH,
    )
    metadata_store = _load_metadata(metadata_path)

    if not force_reindex and _is_unchanged(
        metadata_store,
        metadata["doc_id"],
        checksum,
    ):
        logger.info(
            "Skipping unchanged PDF doc_id=%s",
            metadata["doc_id"],
        )
        return {
            "doc_id": metadata["doc_id"],
            "chunks_indexed": 0,
            "checksum": checksum,
            "status": "skipped",
            "reason": "unchanged",
        }

    docs, metadata = create_documents_from_pdf(str(path))

    if not docs:
        logger.info("Skipping empty PDF doc_id=%s", metadata["doc_id"])
        return {
            "doc_id": metadata["doc_id"],
            "chunks_indexed": 0,
            "checksum": checksum,
            "status": "skipped",
            "reason": "empty_document",
        }

    if vector_store is None:
        _, vector_store, _ = init_embedding_and_vectorstore()
    elif Settings.embed_model is None:
        raise RuntimeError(
            "Settings.embed_model is not initialized when a vector_store "
            "was supplied directly."
        )

    if force_reindex or metadata["doc_id"] in metadata_store:
        _delete_existing_document(vector_store, metadata["doc_id"])

    upsert_documents_to_index(
        docs,
        vector_store,
        service_context=service_context,
    )

    metadata_store[metadata["doc_id"]] = {
        "checksum": checksum,
        "index_version": INDEX_VERSION,
        "source_path": metadata["source_path"],
        "filename": metadata["filename"],
        "page_count": metadata.get("page_count", 0),
        "chunks_indexed": len(docs),
        "indexed_at": now_iso(),
    }
    _save_metadata(metadata_path, metadata_store)

    logger.info(
        "Indexed %d PDF chunks for doc_id=%s",
        len(docs),
        metadata["doc_id"],
    )

    return {
        "doc_id": metadata["doc_id"],
        "chunks_indexed": len(docs),
        "checksum": checksum,
        "status": "indexed",
    }
