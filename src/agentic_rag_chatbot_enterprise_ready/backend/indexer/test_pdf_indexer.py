import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


MODULE_PATH = Path("/mnt/data/pdf_indexer_upgraded.py")


# Dependency-isolated stubs.
fitz = types.ModuleType("fitz")
azure_core_credentials = types.ModuleType("azure.core.credentials")
azure_search_indexes = types.ModuleType("azure.search.documents.indexes")
llama_core = types.ModuleType("llama_index.core")
llama_schema = types.ModuleType("llama_index.core.schema")
llama_embeddings = types.ModuleType("llama_index.embeddings.azure_openai")
llama_vector = types.ModuleType("llama_index.vector_stores.azureaisearch")
app_logger = types.ModuleType("app_logger")


class FakePage:
    def __init__(self, text):
        self.text = text

    def get_text(self, mode="text"):
        assert mode == "text"
        return self.text


class FakePDF:
    def __init__(self, pages):
        self.pages = pages
        self.closed = False

    def __iter__(self):
        return iter(self.pages)

    def __len__(self):
        return len(self.pages)

    @property
    def page_count(self):
        return len(self.pages)

    def close(self):
        self.closed = True


class FakeDocument:
    def __init__(self, text, metadata=None, id_=None):
        self.text = text
        self.metadata = metadata or {}
        self.id_ = id_


class FakeEmbedding:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeCredential:
    def __init__(self, value):
        self.value = value


class FakeSearchIndexClient:
    def __init__(self, endpoint, credential):
        self.endpoint = endpoint
        self.credential = credential


class FakeIndexManagement:
    CREATE_IF_NOT_EXISTS = "create_if_not_exists"


class FakeVectorStore:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.deleted = []
        FakeVectorStore.instances.append(self)

    def delete(self, doc_id):
        self.deleted.append(doc_id)


class FakeStorageContext:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    @classmethod
    def from_defaults(cls, vector_store):
        return cls(vector_store)


class FakeSettings:
    embed_model = None
    chunk_size = None
    chunk_overlap = None


class FakeVectorStoreIndex:
    created = []

    def __init__(self, nodes=None, storage_context=None, **kwargs):
        self.nodes = list(nodes or [])
        self.storage_context = storage_context
        self.kwargs = kwargs
        FakeVectorStoreIndex.created.append(self)


def install_stubs():
    fitz.open = lambda path: FakePDF(
        [FakePage("page one text"), FakePage("page two text")]
    )

    azure_core_credentials.AzureKeyCredential = FakeCredential
    azure_search_indexes.SearchIndexClient = FakeSearchIndexClient

    llama_core.Settings = FakeSettings
    llama_core.StorageContext = FakeStorageContext
    llama_core.VectorStoreIndex = FakeVectorStoreIndex
    llama_schema.Document = FakeDocument

    llama_embeddings.AzureOpenAIEmbedding = FakeEmbedding
    llama_vector.AzureAISearchVectorStore = FakeVectorStore
    llama_vector.IndexManagement = FakeIndexManagement

    app_logger.setup_logger = lambda **kwargs: (Mock(), "test.log")

    sys.modules.update(
        {
            "fitz": fitz,
            "azure": types.ModuleType("azure"),
            "azure.core": types.ModuleType("azure.core"),
            "azure.core.credentials": azure_core_credentials,
            "azure.search": types.ModuleType("azure.search"),
            "azure.search.documents": types.ModuleType("azure.search.documents"),
            "azure.search.documents.indexes": azure_search_indexes,
            "llama_index": types.ModuleType("llama_index"),
            "llama_index.core": llama_core,
            "llama_index.core.schema": llama_schema,
            "llama_index.embeddings": types.ModuleType("llama_index.embeddings"),
            "llama_index.embeddings.azure_openai": llama_embeddings,
            "llama_index.vector_stores": types.ModuleType("llama_index.vector_stores"),
            "llama_index.vector_stores.azureaisearch": llama_vector,
            "app_logger": app_logger,
        }
    )


install_stubs()
spec = importlib.util.spec_from_file_location("pdf_indexer_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.fixture(autouse=True)
def reset_state():
    FakeVectorStore.instances.clear()
    FakeVectorStoreIndex.created.clear()
    FakeSettings.embed_model = None
    FakeSettings.chunk_size = None
    FakeSettings.chunk_overlap = None
    yield


def test_checksum_is_sha256(tmp_path):
    path = tmp_path / "file.pdf"
    path.write_bytes(b"hello")

    assert (
        module.compute_checksum(str(path))
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_chunk_text_exact_offsets():
    result = module.chunk_text(
        "abcdefghij",
        chunk_size=5,
        overlap=2,
    )

    assert result == [
        ("abcde", 0, 5),
        ("defgh", 3, 8),
        ("ghij", 6, 10),
    ]


@pytest.mark.parametrize(
    "chunk_size,overlap",
    [(0, 0), (5, 5), (5, 6), (-1, 0), (5, -1)],
)
def test_chunk_text_rejects_invalid_configuration(chunk_size, overlap):
    with pytest.raises(ValueError):
        module.chunk_text("hello", chunk_size, overlap)


def test_empty_text_returns_no_chunks():
    assert module.chunk_text("") == []


def test_pdf_extraction_closes_document(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"pdf")

    pdf = FakePDF([FakePage("one"), FakePage("two")])
    original = fitz.open
    fitz.open = lambda _: pdf

    try:
        text, page_count = module.extract_text_from_pdf(str(path))
    finally:
        fitz.open = original

    assert text == "one\ntwo"
    assert page_count == 2
    assert pdf.closed is True


def test_pdf_extraction_rejects_non_pdf(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("not pdf")

    with pytest.raises(ValueError):
        module.extract_text_from_pdf(str(path))


def test_page_extraction_produces_offsets(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"pdf")

    pages = module.extract_pdf_pages(str(path))

    assert pages == [
        (1, "page one text", 0, 13),
        (2, "page two text", 14, 27),
    ]


def test_page_range_mapping():
    pages = [
        (1, "abc", 0, 3),
        (2, "def", 4, 7),
    ]

    assert module._page_range_for_chunk(pages, 0, 3) == (1, 1)
    assert module._page_range_for_chunk(pages, 4, 7) == (2, 2)


def test_metadata_contains_stable_document_id(tmp_path):
    path = tmp_path / "example.pdf"
    path.write_bytes(b"pdf")

    metadata1 = module.build_metadata_for_doc(str(path), "checksum")
    metadata2 = module.build_metadata_for_doc(str(path), "checksum")

    assert metadata1["doc_id"] == metadata2["doc_id"]
    assert metadata1["mime_type"] == "application/pdf"
    assert metadata1["index_version"] == module.INDEX_VERSION


def test_create_documents_has_deterministic_ids_and_pages(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"pdf")

    docs, metadata = module.create_documents_from_pdf(str(path))

    assert len(docs) > 0
    assert docs[0].id_ == f"{metadata['doc_id']}::chunk::0"
    assert docs[0].metadata["page_count"] == 2
    assert docs[0].metadata["chunk_start_page"] == 1


def test_create_documents_does_not_mutate_document_metadata(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"pdf")

    docs, metadata = module.create_documents_from_pdf(str(path))

    assert "chunk_id" not in metadata
    assert "indexed_at" not in metadata


def configure_env(monkeypatch):
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://example.openai.azure.com",
    )
    monkeypatch.setenv(
        "AZURE_OPENAI_API_VERSION",
        "2024-10-21",
    )
    monkeypatch.setenv(
        "AZURE_OPENAI_API_KEY",
        "secret",
    )
    monkeypatch.setenv(
        "AZURE_SEARCH_ENDPOINT",
        "https://example.search.windows.net",
    )
    monkeypatch.setenv(
        "AZURE_SEARCH_API_KEY",
        "search-secret",
    )
    monkeypatch.setenv(
        "AZURE_SEARCH_INDEX_NAME",
        "documents",
    )


def test_init_requires_openai_endpoint(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        module.init_embedding_and_vectorstore()


def test_init_uses_current_embedding_configuration(monkeypatch):
    configure_env(monkeypatch)

    embedding, store, service_context = module.init_embedding_and_vectorstore()

    assert isinstance(embedding, FakeEmbedding)
    assert isinstance(store, FakeVectorStore)
    assert service_context is None
    assert FakeSettings.embed_model is embedding
    assert FakeSettings.chunk_size == module.CHUNK_SIZE
    assert FakeSettings.chunk_overlap == module.CHUNK_OVERLAP


def test_init_uses_current_search_client_configuration(monkeypatch):
    configure_env(monkeypatch)

    _, store, _ = module.init_embedding_and_vectorstore()

    assert store.kwargs["index_name"] == "documents"
    assert store.kwargs["index_management"] == "create_if_not_exists"
    assert store.kwargs["embedding_dimensionality"] == 3072


def test_upsert_requires_embedding():
    with pytest.raises(RuntimeError):
        module.upsert_documents_to_index(
            [FakeDocument("hello")],
            FakeVectorStore(),
        )


def test_upsert_uses_current_vector_store_index():
    FakeSettings.embed_model = FakeEmbedding()
    store = FakeVectorStore()

    module.upsert_documents_to_index(
        [FakeDocument("hello")],
        store,
    )

    created = FakeVectorStoreIndex.created[-1]
    assert created.nodes[0].text == "hello"
    assert created.kwargs["insert_batch_size"] == module.EMBED_BATCH_SIZE


def test_upsert_empty_docs_is_noop():
    FakeSettings.embed_model = FakeEmbedding()
    store = FakeVectorStore()

    module.upsert_documents_to_index([], store)

    assert FakeVectorStoreIndex.created == []


def test_index_pdf_rejects_missing_file():
    with pytest.raises(FileNotFoundError):
        module.index_pdf("/missing/file.pdf")


def test_index_pdf_rejects_non_pdf(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("hello")

    with pytest.raises(ValueError):
        module.index_pdf(str(path))


def test_index_pdf_indexes_new_pdf(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("PDF_INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "example.pdf"
    path.write_bytes(b"pdf-content")

    FakeSettings.embed_model = FakeEmbedding()
    store = FakeVectorStore()

    result = module.index_pdf(
        str(path),
        vector_store=store,
    )

    assert result["status"] == "indexed"
    assert result["chunks_indexed"] > 0
    assert result["checksum"]

    metadata = metadata_path.read_text()
    assert result["doc_id"] in metadata


def test_index_pdf_skips_unchanged_pdf(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("PDF_INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "example.pdf"
    path.write_bytes(b"pdf-content")

    FakeSettings.embed_model = FakeEmbedding()
    store = FakeVectorStore()

    first = module.index_pdf(str(path), vector_store=store)
    second = module.index_pdf(str(path), vector_store=store)

    assert first["status"] == "indexed"
    assert second["status"] == "skipped"
    assert second["reason"] == "unchanged"


def test_force_reindex_removes_existing_doc(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("PDF_INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "example.pdf"
    path.write_bytes(b"pdf-content")

    FakeSettings.embed_model = FakeEmbedding()
    store = FakeVectorStore()

    module.index_pdf(str(path), vector_store=store)
    module.index_pdf(
        str(path),
        force_reindex=True,
        vector_store=store,
    )

    assert len(store.deleted) == 1


def test_changed_pdf_is_reindexed(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("PDF_INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "example.pdf"
    path.write_bytes(b"first")

    FakeSettings.embed_model = FakeEmbedding()
    store = FakeVectorStore()

    first = module.index_pdf(str(path), vector_store=store)

    path.write_bytes(b"second")
    second = module.index_pdf(str(path), vector_store=store)

    assert first["checksum"] != second["checksum"]
    assert second["status"] == "indexed"
    assert len(store.deleted) == 1


def test_empty_pdf_is_skipped(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("PDF_INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "empty.pdf"
    path.write_bytes(b"empty")

    original = module.create_documents_from_pdf
    module.create_documents_from_pdf = lambda _: ([], {"doc_id": "empty"})
    try:
        result = module.index_pdf(
            str(path),
            vector_store=FakeVectorStore(),
        )
    finally:
        module.create_documents_from_pdf = original

    assert result["status"] == "skipped"
    assert result["reason"] == "empty_document"


def test_source_does_not_import_legacy_service_context():
    source = MODULE_PATH.read_text()

    assert "from llama_index.core import Document, GPTVectorStoreIndex, ServiceContext" not in source
    assert "ServiceContext.from_defaults" not in source
    assert "GPTVectorStoreIndex.from_documents" not in source


def test_source_uses_current_vector_store_index():
    source = MODULE_PATH.read_text()

    assert "VectorStoreIndex(" in source
    assert "StorageContext.from_defaults" in source


def test_source_uses_timezone_aware_datetime():
    source = MODULE_PATH.read_text()

    assert "datetime.now(timezone.utc)" in source


def test_source_streams_checksum():
    source = MODULE_PATH.read_text()

    assert "1024 * 1024" in source
    assert "handle.read" in source


def test_source_closes_pdf_document():
    source = MODULE_PATH.read_text()

    assert "finally:" in source
    assert "document.close()" in source


def test_source_uses_current_azure_search_client():
    source = MODULE_PATH.read_text()

    assert "SearchIndexClient(" in source
    assert "search_or_index_client=search_index_client" in source
    assert "IndexManagement.CREATE_IF_NOT_EXISTS" in source
