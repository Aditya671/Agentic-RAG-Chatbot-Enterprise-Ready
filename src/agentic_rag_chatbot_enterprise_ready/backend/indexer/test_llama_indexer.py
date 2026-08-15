import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest


MODULE_PATH = Path("/mnt/data/llama_indexer_upgraded.py")


# Dependency-isolated stubs.
fitz = types.ModuleType("fitz")
docx_module = types.ModuleType("docx")
azure_core_credentials = types.ModuleType("azure.core.credentials")
azure_search_indexes = types.ModuleType("azure.search.documents.indexes")
llama_core = types.ModuleType("llama_index.core")
llama_schema = types.ModuleType("llama_index.core.schema")
llama_embeddings = types.ModuleType("llama_index.embeddings.azure_openai")
llama_vector = types.ModuleType("llama_index.vector_stores.azureaisearch")
app_logger = types.ModuleType("app_logger")


class FakePDFPage:
    def __init__(self, text):
        self._text = text

    def get_text(self, mode):
        assert mode == "text"
        return self._text


class FakePDF:
    def __init__(self, pages):
        self.pages = pages
        self.closed = False

    def __iter__(self):
        return iter(self.pages)

    def __len__(self):
        return len(self.pages)

    def close(self):
        self.closed = True


class FakeEmbedding:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeSearchIndexClient:
    def __init__(self, endpoint, credential):
        self.endpoint = endpoint
        self.credential = credential


class FakeCredential:
    def __init__(self, value):
        self.value = value


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
    llm = None
    chunk_size = None
    chunk_overlap = None


class FakeVectorStoreIndex:
    created = []
    queries = []

    def __init__(self, nodes=None, storage_context=None, **kwargs):
        self.nodes = list(nodes or [])
        self.storage_context = storage_context
        self.kwargs = kwargs
        FakeVectorStoreIndex.created.append(self)

    @classmethod
    def from_vector_store(cls, vector_store, embed_model=None):
        instance = cls(nodes=[], storage_context=FakeStorageContext(vector_store))
        instance.embed_model = embed_model
        return instance

    def as_query_engine(self, similarity_top_k):
        FakeVectorStoreIndex.queries.append(similarity_top_k)
        return types.SimpleNamespace(
            query=lambda query: {"query": query, "top_k": similarity_top_k}
        )


class FakeDocument:
    def __init__(self, text, metadata=None, id_=None):
        self.text = text
        self.metadata = metadata or {}
        self.id_ = id_


def setup_stubs():
    fitz.open = lambda path: FakePDF(
        [FakePDFPage("page one"), FakePDFPage("page two")]
    )
    docx_module.Document = lambda path: types.SimpleNamespace(
        paragraphs=[
            types.SimpleNamespace(text="paragraph one"),
            types.SimpleNamespace(text=""),
            types.SimpleNamespace(text="paragraph two"),
        ]
    )

    azure_core_credentials.AzureKeyCredential = FakeCredential
    azure_search_indexes.SearchIndexClient = FakeSearchIndexClient

    llama_core.Settings = FakeSettings
    llama_core.StorageContext = FakeStorageContext
    llama_core.VectorStoreIndex = FakeVectorStoreIndex
    llama_schema.Document = FakeDocument

    llama_embeddings.AzureOpenAIEmbedding = FakeEmbedding

    class FakeIndexManagement:
        CREATE_IF_NOT_EXISTS = "create_if_not_exists"

    llama_vector.AzureAISearchVectorStore = FakeVectorStore
    llama_vector.IndexManagement = FakeIndexManagement

    app_logger.setup_logger = lambda **kwargs: (Mock(), "test.log")

    sys.modules.update(
        {
            "fitz": fitz,
            "docx": docx_module,
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


setup_stubs()
spec = importlib.util.spec_from_file_location("llama_indexer_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    FakeVectorStore.instances.clear()
    FakeVectorStoreIndex.created.clear()
    FakeVectorStoreIndex.queries.clear()
    monkeypatch.setattr(module, "Settings", FakeSettings)
    yield


def test_chunking_exact_offsets():
    chunks = module.chunk_text_simple("abcdefghij", chunk_size=5, overlap=2)

    assert chunks == [
        ("abcde", 0, 5),
        ("defgh", 3, 8),
        ("ghij", 6, 10),
    ]


@pytest.mark.parametrize(
    "chunk_size,overlap",
    [(0, 0), (5, 5), (5, 6), (-1, 0), (5, -1)],
)
def test_chunking_rejects_invalid_parameters(chunk_size, overlap):
    with pytest.raises(ValueError):
        module.chunk_text_simple("abc", chunk_size, overlap)


def test_empty_text_has_no_chunks():
    assert module.chunk_text_simple("") == []


def test_pdf_resource_is_closed():
    pdf = FakePDF([FakePDFPage("hello")])
    original = fitz.open
    fitz.open = lambda path: pdf
    try:
        text, pages = module.extract_text_from_pdf("file.pdf")
    finally:
        fitz.open = original

    assert text == "hello"
    assert pages == 1
    assert pdf.closed is True


def test_docx_extraction_ignores_empty_paragraphs():
    text, _ = module.extract_text_from_docx("file.docx")
    assert text == "paragraph one\nparagraph two"


def test_csv_column_validation():
    dataframe = pd.DataFrame({"a": [1], "b": [2]})

    with pytest.raises(ValueError):
        module.extract_text_from_dataframe(
            dataframe,
            text_columns=["missing"],
        )


def test_csv_max_rows_validation():
    dataframe = pd.DataFrame({"a": [1], "b": [2]})

    with pytest.raises(ValueError):
        module.extract_text_from_dataframe(dataframe, max_rows=-1)


def test_dataframe_conversion():
    dataframe = pd.DataFrame({"name": ["A", "B"]})

    text, _ = module.extract_text_from_dataframe(dataframe)

    assert "name" in text
    assert "A" in text
    assert "B" in text


def test_checksum_bytes_is_sha256():
    assert (
        module.compute_checksum_bytes(b"hello")
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_document_ids_are_deterministic():
    assert module.make_doc_id("same") == module.make_doc_id("same")
    assert module.make_doc_id("same") != module.make_doc_id("different")


def test_document_builder_uses_deterministic_chunk_ids():
    docs = module.create_documents_from_text(
        "abcdefghij",
        {"doc_id": "doc-1", "filename": "x.txt"},
        chunk_size=5,
        overlap=0,
    )

    assert [doc.id_ for doc in docs] == [
        "doc-1::chunk::0",
        "doc-1::chunk::1",
    ]
    assert docs[0].metadata["chunk_start_offset"] == 0
    assert docs[1].metadata["chunk_start_offset"] == 5


def test_document_builder_does_not_mutate_base_metadata():
    metadata = {"doc_id": "doc-1", "filename": "x.txt"}

    module.create_documents_from_text("hello", metadata)

    assert metadata == {"doc_id": "doc-1", "filename": "x.txt"}


def test_document_builder_requires_doc_id():
    with pytest.raises(ValueError):
        module.create_documents_from_text("hello", {})


def test_init_requires_required_environment(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        module.init_embedding_and_vectorstore()


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


def test_init_uses_current_lamaindex_api(monkeypatch):
    configure_env(monkeypatch)

    embedding, store, service_context = module.init_embedding_and_vectorstore()

    assert isinstance(embedding, FakeEmbedding)
    assert isinstance(store, FakeVectorStore)
    assert service_context is None
    assert FakeSettings.embed_model is embedding
    assert FakeSettings.chunk_size == module.CHUNK_SIZE


def test_init_configures_azure_search_client(monkeypatch):
    configure_env(monkeypatch)

    _, store, _ = module.init_embedding_and_vectorstore()

    assert store.kwargs["index_name"] == "documents"
    assert store.kwargs["index_management"] == "create_if_not_exists"
    assert store.kwargs["embedding_dimensionality"] == 3072


def test_index_file_rejects_missing_file():
    with pytest.raises(FileNotFoundError):
        module.index_file("/does/not/exist.txt")


def test_index_file_rejects_unsupported_type(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"binary")

    with pytest.raises(ValueError, match="Unsupported file type"):
        module.index_file(str(path), vector_store=FakeVectorStore())


def test_index_file_indexes_text_file(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "example.txt"
    path.write_text("hello world")

    store = FakeVectorStore()

    result = module.index_file(
        str(path),
        vector_store=store,
    )

    assert result["status"] == "indexed"
    assert result["chunks_indexed"] == 1
    assert result["checksum"]
    assert FakeVectorStoreIndex.created[-1].nodes[0].text == "hello world"


def test_index_file_skips_unchanged_document(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "example.txt"
    path.write_text("hello world")

    store = FakeVectorStore()

    first = module.index_file(str(path), vector_store=store)
    second = module.index_file(str(path), vector_store=store)

    assert first["status"] == "indexed"
    assert second["status"] == "skipped"
    assert second["reason"] == "unchanged"


def test_force_reindex_removes_existing_document(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "example.txt"
    path.write_text("hello world")

    store = FakeVectorStore()

    module.index_file(str(path), vector_store=store)
    module.index_file(str(path), force_reindex=True, vector_store=store)

    assert len(store.deleted) == 1


def test_empty_document_is_skipped(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("INDEX_METADATA_PATH", str(metadata_path))

    path = tmp_path / "empty.txt"
    path.write_text("")

    result = module.index_file(
        str(path),
        vector_store=FakeVectorStore(),
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "empty_document"


def test_index_dataframe():
    dataframe = pd.DataFrame({"name": ["A", "B"]})
    store = FakeVectorStore()

    result = module.index_dataframe(
        dataframe,
        name="test-data",
        vector_store=store,
    )

    assert result["status"] == "indexed"
    assert result["chunks_indexed"] > 0


def test_semantic_search_validates_query_and_top_k():
    store = FakeVectorStore()

    with pytest.raises(ValueError):
        module.semantic_search("", vector_store=store)

    with pytest.raises(ValueError):
        module.semantic_search("hello", top_k=0, vector_store=store)


def test_semantic_search_passes_top_k():
    store = FakeVectorStore()

    result = module.semantic_search(
        "hello",
        top_k=7,
        vector_store=store,
    )

    assert result["query"] == "hello"
    assert result["top_k"] == 7
    assert FakeVectorStoreIndex.queries[-1] == 7


def test_index_path_processes_supported_files(tmp_path, monkeypatch):
    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setenv("INDEX_METADATA_PATH", str(metadata_path))

    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "ignored.bin").write_bytes(b"x")

    store = FakeVectorStore()
    monkeypatch.setattr(
        module,
        "init_embedding_and_vectorstore",
        lambda: (FakeEmbedding(), store, None),
    )

    results = module.index_path(str(tmp_path), recursive=False)

    assert len(results) == 2
    assert all(result["status"] == "indexed" for result in results)


def test_index_path_reports_file_failure_without_aborting(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("a")

    store = FakeVectorStore()
    monkeypatch.setattr(
        module,
        "index_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        module,
        "init_embedding_and_vectorstore",
        lambda: (FakeEmbedding(), store, None),
    )

    results = module.index_path(str(tmp_path))

    assert results == [
        {
            "source_path": str(tmp_path / "a.txt"),
            "status": "failed",
        }
    ]


def test_source_has_no_legacy_service_context_import_or_usage():
    source = MODULE_PATH.read_text()

    assert "from llama_index.core.schema import Document, ServiceContext" not in source
    assert "ServiceContext.from_defaults" not in source
    assert "GPTVectorStoreIndex.from_documents" not in source
    assert "from llama_index.core import GPTVectorStoreIndex" not in source


def test_source_uses_current_vector_store_index():
    source = MODULE_PATH.read_text()

    assert "VectorStoreIndex" in source
    assert "VectorStoreIndex.from_vector_store" in source


def test_source_closes_pdf_resources():
    source = MODULE_PATH.read_text()

    assert "finally:" in source
    assert "document.close()" in source


def test_source_uses_timezone_aware_datetime():
    source = MODULE_PATH.read_text()

    assert "datetime.now(timezone.utc)" in source


def test_source_does_not_use_read_all_for_file_checksum():
    source = MODULE_PATH.read_text()

    assert 'f.read())' not in source


def test_source_applies_top_k_to_query_engine():
    source = MODULE_PATH.read_text()

    assert "as_query_engine(similarity_top_k=top_k)" in source


def test_source_uses_deterministic_document_ids():
    source = MODULE_PATH.read_text()

    assert "uuid.uuid5(uuid.NAMESPACE_URL" in source


def test_source_uses_current_azure_search_client_constructor():
    source = MODULE_PATH.read_text()

    assert "search_or_index_client=client" in source
    assert "IndexManagement.CREATE_IF_NOT_EXISTS" in source
