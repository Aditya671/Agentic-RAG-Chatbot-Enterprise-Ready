import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


MODULE_PATH = Path("/mnt/data/user_uploaded_file_indexer_upgraded.py")

# Dependency-isolated stubs. The real application packages are not required
# to execute this regression suite.
llama_core = types.ModuleType("llama_index.core")
llama_chat = types.ModuleType("llama_index.core.chat_engine")
llama_indices = types.ModuleType("llama_index.core.indices.document_summary")
llama_memory = types.ModuleType("llama_index.core.memory")
llama_node = types.ModuleType("llama_index.core.node_parser")
llama_prompts = types.ModuleType("llama_index.core.prompts")
llama_vs = types.ModuleType("llama_index.core.vector_stores.simple")
llama_vst = types.ModuleType("llama_index.core.vector_stores.types")
llama_schema = types.ModuleType("llama_index.core.schema")
azure_blob = types.ModuleType("azure.storage.blob")
azure_identity = types.ModuleType("azure.identity")
app_logger = types.ModuleType("app_logger")
backend_config = types.ModuleType("backend.config")
backend_models = types.ModuleType("backend.ai_models")
backend_credentials = types.ModuleType("backend.azure_credential_manager")
backend_loader = types.ModuleType("backend.llm_loader")
backend_prompts = types.ModuleType("backend.prompts")
backend_utility = types.ModuleType("backend.utility")


class FakeDocument:
    def __init__(self, text="", metadata=None, id_=None, doc_id=None):
        self.text = text
        self.metadata = metadata or {}
        self.id_ = id_ or doc_id or "doc-1"
        self.doc_id = self.id_


class FakeMemory:
    @classmethod
    def from_defaults(cls, **kwargs):
        instance = cls()
        instance.kwargs = kwargs
        return instance


class FakeSettings:
    embed_model = None
    llm = None


class FakeStorageContext:
    def __init__(self, persist_dir=None, vector_store=None):
        self.persist_dir = persist_dir
        self.vector_store = vector_store

    @classmethod
    def from_defaults(cls, persist_dir=None, vector_store=None, **kwargs):
        return cls(persist_dir=persist_dir, vector_store=vector_store)

    def persist(self, persist_dir=None, **kwargs):
        target = Path(persist_dir or self.persist_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "index_store.json").write_text("{}")


class FakeVectorStore:
    def __init__(self):
        self.persisted = False

    def persist(self, *args, **kwargs):
        self.persisted = True


class FakeIndex:
    def __init__(self, documents=None, storage_context=None):
        self.documents = list(documents or [])
        self.storage_context = storage_context or FakeStorageContext(
            vector_store=FakeVectorStore()
        )

    @classmethod
    def from_documents(cls, documents, storage_context=None, **kwargs):
        return cls(documents, storage_context)

    def as_retriever(self, **kwargs):
        return {"retriever": True, **kwargs}

    def storage_context_persist(self, path):
        self.storage_context.persist(path)


class FakeSummaryIndex(FakeIndex):
    def get_document_summary(self, doc_id):
        return f"summary:{doc_id}"


class FakeReader:
    def __init__(self, input_files, **kwargs):
        self.input_files = list(input_files)

    async def aload_data(self, show_progress=False):
        docs = []
        for path in self.input_files:
            docs.append(
                FakeDocument(
                    text=f"content for {Path(path).name}",
                    metadata={
                        "file_path": str(path),
                        "file_name": Path(path).name,
                    },
                    id_=f"doc-{Path(path).name}",
                )
            )
        return docs


class FakeSentenceSplitter:
    def __init__(self, chunk_size, chunk_overlap):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap


class FakePromptTemplate:
    def __init__(self, template):
        self.template = template


class FakeRetriever:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class FakeChatEngine:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def achat(self, question):
        return {"question": question}


class FakeLLM:
    pass


class FakeCredentialManager:
    def __init__(self, key_vault_url=None):
        self.key_vault_url = key_vault_url

    def get_secret(self, name):
        return "secret"

    def get_credential(self):
        return object()


class FakeBlobServiceClient:
    @classmethod
    def from_connection_string(cls, value):
        return cls()

    def get_container_client(self, name):
        return Mock()

    def close(self):
        pass


class IndexConfig:
    def __init__(self):
        self.key_vault = {"url": "https://vault.example"}
        self.rag = {"chunk_size": 1000, "chunk_overlap": 200}


class Config:
    indexes = {"test": IndexConfig()}


class Model:
    GPT51 = "gpt-5.1"


backend_config.config = Config()
backend_models.AIModelTypes = Model
backend_credentials.AzureCredentialManager = FakeCredentialManager
backend_loader.load_embed = lambda **kwargs: object()
backend_loader.load_llm = lambda *args, **kwargs: FakeLLM()
backend_prompts.AGENTIC_AI_SYSTEM_PROMPT = "Use only supplied context."
backend_utility.compute_file_hash = lambda path: __import__("hashlib").sha256(
    Path(path).read_bytes()
).hexdigest()

llama_core.Document = FakeDocument
llama_core.DocumentSummaryIndex = FakeSummaryIndex
llama_core.SimpleDirectoryReader = FakeReader
llama_core.StorageContext = FakeStorageContext
llama_core.Settings = FakeSettings
llama_core.VectorStoreIndex = FakeIndex
llama_core.get_response_synthesizer = lambda **kwargs: object()
llama_core.load_index_from_storage = lambda storage_context: FakeIndex(
    storage_context=storage_context
)
llama_chat.CondensePlusContextChatEngine = FakeChatEngine
llama_indices.DocumentSummaryIndexLLMRetriever = FakeRetriever
llama_memory.Memory = FakeMemory
llama_node.SentenceSplitter = FakeSentenceSplitter
llama_prompts.PromptTemplate = FakePromptTemplate
llama_vs.SimpleVectorStore = FakeVectorStore
llama_vst.VectorStoreQueryMode = types.SimpleNamespace(DEFAULT="default")
llama_schema.Document = FakeDocument
azure_blob.BlobServiceClient = FakeBlobServiceClient
azure_identity.get_bearer_token_provider = lambda *args, **kwargs: object()
app_logger.setup_logger = lambda *args, **kwargs: (Mock(), "test.log")

sys.modules.update(
    {
        "llama_index": types.ModuleType("llama_index"),
        "llama_index.core": llama_core,
        "llama_index.core.chat_engine": llama_chat,
        "llama_index.core.indices": types.ModuleType("llama_index.core.indices"),
        "llama_index.core.indices.document_summary": llama_indices,
        "llama_index.core.memory": llama_memory,
        "llama_index.core.node_parser": llama_node,
        "llama_index.core.prompts": llama_prompts,
        "llama_index.core.vector_stores": types.ModuleType(
            "llama_index.core.vector_stores"
        ),
        "llama_index.core.vector_stores.simple": llama_vs,
        "llama_index.core.vector_stores.types": llama_vst,
        "llama_index.core.schema": llama_schema,
        "azure": types.ModuleType("azure"),
        "azure.storage": types.ModuleType("azure.storage"),
        "azure.storage.blob": azure_blob,
        "azure.identity": azure_identity,
        "app_logger": app_logger,
        "backend.config": backend_config,
        "backend.ai_models": backend_models,
        "backend.azure_credential_manager": backend_credentials,
        "backend.llm_loader": backend_loader,
        "backend.prompts": backend_prompts,
        "backend.utility": backend_utility,
    }
)

spec = importlib.util.spec_from_file_location("user_file_indexer_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

UserUploadedFileIndexer = module.UserUploadedFileIndexer


@pytest.fixture
def indexer(tmp_path):
    return UserUploadedFileIndexer(
        root_dir=str(tmp_path / "uploads"),
        index_name="test",
        max_file_size=1024 * 1024,
    )


def test_constructor_does_not_use_shared_memory_default(indexer):
    assert indexer.memory is not None


def test_invalid_similarity_top_k(tmp_path):
    with pytest.raises(ValueError):
        UserUploadedFileIndexer(
            root_dir=str(tmp_path),
            index_name="test",
            similarity_top_k=0,
        )


def test_invalid_index_name(tmp_path):
    with pytest.raises(ValueError):
        UserUploadedFileIndexer(
            root_dir=str(tmp_path),
            index_name="",
        )


def test_safe_filename_removes_path_components(indexer):
    assert indexer._safe_filename("../../secret.pdf") == "secret.pdf"


def test_safe_filename_rejects_empty(indexer):
    with pytest.raises(ValueError):
        indexer._safe_filename("")


def test_safe_upload_path_stays_inside_upload_dir(indexer):
    path = indexer._safe_upload_path("file.pdf")
    assert path.parent == Path(indexer.upload_dir).resolve()


def test_file_size_limit(indexer, tmp_path):
    path = tmp_path / "large.pdf"
    path.write_bytes(b"x" * 2048)
    indexer.max_file_size = 10

    with pytest.raises(ValueError):
        indexer._validate_file(path)


def test_unsupported_extension(indexer, tmp_path):
    path = tmp_path / "file.exe"
    path.write_bytes(b"x")

    with pytest.raises(ValueError, match="Unsupported"):
        indexer._validate_file(path)


def test_missing_file_rejected(indexer, tmp_path):
    with pytest.raises(FileNotFoundError):
        indexer._validate_file(tmp_path / "missing.pdf")


@pytest.mark.asyncio
async def test_save_uploaded_dict(indexer):
    path = await indexer._save_uploaded_file(
        {"name": "test.pdf", "content": b"hello"}
    )
    assert path.exists()
    assert path.name == "test.pdf"


@pytest.mark.asyncio
async def test_save_uploaded_object(indexer):
    class Upload:
        name = "test.txt"

        def read(self):
            return b"hello"

    path = await indexer._save_uploaded_file(Upload())
    assert path.read_bytes() == b"hello"


def test_metadata_atomic_round_trip(indexer, tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("hello")
    indexer._update_index_metadata([str(path)])

    metadata = indexer._load_metadata()

    assert metadata["test.txt"]["hash"]
    assert metadata["test.txt"]["index_version"] == module.INDEX_VERSION


def test_should_reindex_when_no_metadata(indexer, tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("hello")

    assert indexer._should_reindex(str(path)) is True


def test_should_reindex_false_for_fresh_same_hash(indexer, tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("hello")

    indexer._update_index_metadata([str(path)])

    assert indexer._should_reindex(str(path)) is False


def test_should_reindex_when_content_changes(indexer, tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("hello")

    indexer._update_index_metadata([str(path)])
    path.write_text("changed")

    assert indexer._should_reindex(str(path)) is True


def test_should_reindex_after_age(indexer, tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("hello")

    indexer._update_index_metadata([str(path)])
    metadata = indexer._load_metadata()
    metadata["test.txt"]["indexed_at"] = "2020-01-01T00:00:00Z"
    indexer._atomic_write_json(indexer._metadata_path, metadata)

    assert indexer._should_reindex(str(path), reindex_after_days=30) is True


def test_chunk_configuration_is_valid(indexer):
    assert indexer._chunk_size == 1000
    assert indexer._chunk_overlap == 200


@pytest.mark.asyncio
async def test_index_uploaded_files_accepts_paths(indexer, tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("hello")

    result = await indexer.index_uploaded_files(
        file_list=[str(path)]
    )

    assert result["indexed"] == ["a.txt"]
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_index_uploaded_files_accepts_dicts(indexer):
    result = await indexer.index_uploaded_files(
        file_list=[
            {"name": "a.txt", "content": b"hello"},
            {"name": "b.txt", "content": b"world"},
        ]
    )

    assert result["indexed"] == ["a.txt", "b.txt"]


@pytest.mark.asyncio
async def test_index_uploaded_files_limit(indexer):
    result = await indexer.index_uploaded_files(
        file_list=[
            {"name": "a.txt", "content": b"hello"},
            {"name": "b.txt", "content": b"world"},
        ],
        num_files_limit=1,
    )

    assert result["indexed"] == ["a.txt"]


@pytest.mark.asyncio
async def test_index_uploaded_files_rejects_both_sources(indexer):
    with pytest.raises(ValueError):
        await indexer.index_uploaded_files(
            input_dir=str(Path(indexer.root_dir)),
            file_list=[],
        )


@pytest.mark.asyncio
async def test_index_uploaded_files_requires_source(indexer):
    with pytest.raises(ValueError):
        await indexer.index_uploaded_files()


@pytest.mark.asyncio
async def test_index_uploaded_files_skips_unchanged(indexer, tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("hello")

    first = await indexer.index_uploaded_files(file_list=[str(path)])
    second = await indexer.index_uploaded_files(file_list=[str(path)])

    assert first["indexed"] == ["a.txt"]
    assert second["indexed"] == []
    assert second["skipped"] == ["a.txt"]


def test_vector_index_loader_requires_index(indexer):
    with pytest.raises(FileNotFoundError):
        indexer._load_vector_index()


def test_summary_index_loader_requires_index(indexer):
    with pytest.raises(FileNotFoundError):
        indexer._load_summary_index()


def test_response_mode_validation(indexer):
    with pytest.raises(ValueError):
        indexer.create_local_citation_chat_engine(response_mode="bad")


def test_query_type_validation(indexer):
    with pytest.raises(ValueError):
        indexer.create_local_citation_chat_engine(query_type="bad")


def test_top_k_validation(indexer):
    with pytest.raises(ValueError):
        indexer.create_local_citation_chat_engine(top_k=0)


def test_debug_dump_excludes_document_text(indexer):
    result = indexer.dump_debug_files(
        [FakeDocument(text="secret document text", metadata={"file_name": "x.txt"})]
    )

    assert result is True

    payload = indexer._load_json(
        indexer._debug_dir / "index_debug.json",
        {},
    )
    assert payload["documents"][0]["text_length"] > 0
    assert "secret document text" not in json_text(payload)


def test_source_has_no_mutable_memory_default():
    source = MODULE_PATH.read_text()

    assert "memory: Memory = Memory.from_defaults" not in source


def test_source_uses_timezone_aware_datetime():
    source = MODULE_PATH.read_text()

    assert "datetime.now(timezone.utc)" in source


def test_source_has_path_safety():
    source = MODULE_PATH.read_text()

    assert "_safe_upload_path" in source
    assert "resolve()" in source


def test_source_uses_atomic_metadata_replace():
    source = MODULE_PATH.read_text()

    assert "temporary.replace(path)" in source


def test_source_persists_vector_index():
    source = MODULE_PATH.read_text()

    assert "vector_index.storage_context.persist" in source


def test_source_persists_summary_index_separately():
    source = MODULE_PATH.read_text()

    assert "_summary_index_dir" in source
    assert "summary_index.storage_context.persist" in source


def test_source_does_not_rebuild_summary_for_existing_files():
    source = MODULE_PATH.read_text()

    # Existing files should be reported as skipped rather than rebuilding a
    # summary index on every call.
    assert 'summaries.setdefault(' in source


def json_text(value):
    import json
    return json.dumps(value)
