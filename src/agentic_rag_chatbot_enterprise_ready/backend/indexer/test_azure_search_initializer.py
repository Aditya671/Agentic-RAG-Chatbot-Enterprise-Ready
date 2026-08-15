import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

MODULE_PATH = Path("/mnt/data/azure_search_initializer_upgraded.py")

# ---------------------------------------------------------------------------
# Dependency-isolated stubs. The tests verify the module contract without
# requiring Azure credentials, a live Search service, or LlamaIndex.
# ---------------------------------------------------------------------------

azure_search = types.ModuleType("azure.search.documents")
azure_search_aio = types.ModuleType("azure.search.documents.aio")
azure_indexes = types.ModuleType("azure.search.documents.indexes")
azure_indexes_aio = types.ModuleType("azure.search.documents.indexes.aio")

llama_core = types.ModuleType("llama_index.core")
llama_embeddings_azure = types.ModuleType("llama_index.embeddings.azure_openai")
llama_embeddings_openai = types.ModuleType("llama_index.embeddings.openai")
llama_vector = types.ModuleType("llama_index.vector_stores.azureaisearch")

azure = types.ModuleType("azure")
azure_search_pkg = types.ModuleType("azure.search")
llama = types.ModuleType("llama_index")
llama_embeddings = types.ModuleType("llama_index.embeddings")
llama_vector_pkg = types.ModuleType("llama_index.vector_stores")


class FakeSearchClient:
    instances = []

    def __init__(self, endpoint, index_name, credential):
        self.endpoint = endpoint
        self.index_name = index_name
        self.credential = credential
        self.closed = False
        self.__class__.instances.append(self)

    async def close(self):
        self.closed = True


class FakeSearchIndexClient:
    instances = []

    def __init__(self, endpoint, credential):
        self.endpoint = endpoint
        self.credential = credential
        self.closed = False
        self.__class__.instances.append(self)

    def close(self):
        self.closed = True


class FakeAsyncSearchIndexClient(FakeSearchIndexClient):
    pass


class FakeVectorStore:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.__class__.instances.append(self)




# A class-like enum is needed for isinstance(..., IndexManagement).
class IndexManagement:
    VALIDATE_INDEX = None
    CREATE_IF_NOT_EXISTS = None

    def __init__(self, value):
        if value not in {"validate_index", "create_if_not_exists"}:
            raise ValueError(value)
        self.value = value

    def __eq__(self, other):
        return isinstance(other, IndexManagement) and self.value == other.value


IndexManagement.VALIDATE_INDEX = IndexManagement("validate_index")
IndexManagement.CREATE_IF_NOT_EXISTS = IndexManagement("create_if_not_exists")

class FakeStorageContext:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    @classmethod
    def from_defaults(cls, vector_store=None):
        return cls(vector_store)


class FakeSettings:
    llm = None
    embed_model = None


class FakeVectorStoreIndex:
    def __init__(self, storage_context):
        self.storage_context = storage_context

    @classmethod
    def from_documents(cls, documents, storage_context, llm, embed_model):
        assert documents == []
        assert llm is not None
        assert embed_model is not None
        return cls(storage_context)


class FakeAzureEmbedding:
    pass


class FakeOpenAIEmbedding:
    pass


azure_search.SearchClient = FakeSearchClient
azure_search_aio.SearchClient = FakeSearchClient
azure_indexes.SearchIndexClient = FakeSearchIndexClient
azure_indexes_aio.SearchIndexClient = FakeAsyncSearchIndexClient

llama_core.Settings = FakeSettings
llama_core.StorageContext = FakeStorageContext
llama_core.VectorStoreIndex = FakeVectorStoreIndex

llama_embeddings_azure.AzureOpenAIEmbedding = FakeAzureEmbedding
llama_embeddings_openai.OpenAIEmbedding = FakeOpenAIEmbedding

llama_vector.AzureAISearchVectorStore = FakeVectorStore
llama_vector.IndexManagement = IndexManagement

sys.modules.update(
    {
        "azure": azure,
        "azure.search": azure_search_pkg,
        "azure.search.documents": azure_search,
        "azure.search.documents.aio": azure_search_aio,
        "azure.search.documents.indexes": azure_indexes,
        "azure.search.documents.indexes.aio": azure_indexes_aio,
        "llama_index": llama,
        "llama_index.core": llama_core,
        "llama_index.embeddings": llama_embeddings,
        "llama_index.embeddings.azure_openai": llama_embeddings_azure,
        "llama_index.embeddings.openai": llama_embeddings_openai,
        "llama_index.vector_stores": llama_vector_pkg,
        "llama_index.vector_stores.azureaisearch": llama_vector,
    }
)

spec = importlib.util.spec_from_file_location(
    "azure_search_initializer_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.fixture(autouse=True)
def reset_stubs():
    FakeSearchClient.instances.clear()
    FakeSearchIndexClient.instances.clear()
    FakeVectorStore.instances.clear()
    FakeSettings.llm = None
    FakeSettings.embed_model = None
    yield


def make_args(**overrides):
    args = {
        "search_index_name": "test-index",
        "llm": object(),
        "embed_model": FakeAzureEmbedding(),
        "embed_size": 1536,
        "search_service_endpoint": "https://example.search.windows.net",
        "search_service_credential": object(),
    }
    args.update(overrides)
    return args


def test_module_imports_without_nest_asyncio():
    source = MODULE_PATH.read_text()
    assert "import nest_asyncio" not in source
    assert "nest_asyncio.apply" not in source


def test_module_does_not_create_global_azure_credential():
    source = MODULE_PATH.read_text()
    assert "DefaultAzureCredential()" not in source


def test_initialize_sync_uses_search_index_client():
    index = module.initialize_index(**make_args())

    assert isinstance(index, FakeVectorStoreIndex)
    assert len(FakeSearchIndexClient.instances) == 1
    assert len(FakeSearchClient.instances) == 0

    client = FakeSearchIndexClient.instances[0]
    assert client.endpoint == "https://example.search.windows.net"

    store = FakeVectorStore.instances[0]
    assert store.kwargs["index_name"] == "test-index"
    assert store.kwargs["index_management"] == IndexManagement.VALIDATE_INDEX


def test_initialize_async_uses_async_search_client():
    index = module.initialize_index(**make_args(aio=True))

    assert len(FakeSearchClient.instances) == 1
    client = FakeSearchClient.instances[0]

    assert client.index_name == "test-index"

    store = FakeVectorStore.instances[0]
    assert store.kwargs["search_or_index_client"] is client
    assert store.kwargs["index_name"] is None


def test_default_index_management_validates_existing_index():
    module.initialize_index(**make_args())

    store = FakeVectorStore.instances[0]
    assert store.kwargs["index_management"] == IndexManagement.VALIDATE_INDEX


def test_create_if_not_exists_can_be_requested():
    module.initialize_index(
        **make_args(
            index_management=IndexManagement.CREATE_IF_NOT_EXISTS
        )
    )

    store = FakeVectorStore.instances[0]
    assert (
        store.kwargs["index_management"]
        == IndexManagement.CREATE_IF_NOT_EXISTS
    )


def test_string_index_management_is_supported():
    module.initialize_index(
        **make_args(index_management="create_if_not_exists")
    )

    store = FakeVectorStore.instances[0]
    assert (
        store.kwargs["index_management"]
        == IndexManagement.CREATE_IF_NOT_EXISTS
    )


def test_invalid_index_management_is_rejected():
    with pytest.raises(ValueError, match="Unsupported index_management"):
        module.initialize_index(
            **make_args(index_management="bogus")
        )


def test_unexpected_kwargs_are_rejected():
    with pytest.raises(TypeError, match="Unexpected keyword"):
        module.initialize_index(**make_args(unexpected=True))


def test_missing_llm_is_rejected():
    with pytest.raises(ValueError, match="llm must be provided"):
        module.initialize_index(**make_args(llm=None))


def test_missing_embedding_is_rejected():
    with pytest.raises(ValueError, match="embed_model must be provided"):
        module.initialize_index(**make_args(embed_model=None))


def test_invalid_embedding_dimension_is_rejected():
    with pytest.raises(ValueError, match="embed_size"):
        module.initialize_index(**make_args(embed_size=0))


def test_empty_index_name_is_rejected():
    with pytest.raises(ValueError, match="search_index_name"):
        module.initialize_index(**make_args(search_index_name=""))


def test_empty_endpoint_is_rejected():
    with pytest.raises(ValueError, match="search_service_endpoint"):
        module.initialize_index(**make_args(search_service_endpoint=""))


def test_missing_credential_is_rejected():
    with pytest.raises(ValueError, match="search_service_credential"):
        module.initialize_index(
            **make_args(search_service_credential=None)
        )


def test_new_schema_mapping_is_preserved():
    module.initialize_index(**make_args())

    params = FakeVectorStore.instances[0].kwargs

    assert params["id_field_key"] == "id"
    assert params["chunk_field_key"] == "chunk"
    assert params["embedding_field_key"] == "embedding"
    assert params["doc_id_field_key"] == "doc_id"
    assert params["embedding_dimensionality"] == 1536
    assert params["vector_algorithm_type"] == "exhaustiveKnn"


def test_old_schema_mapping_is_preserved():
    module.initialize_index(**make_args(old_index=True))

    params = FakeVectorStore.instances[0].kwargs

    assert params["chunk_field_key"] == "content"
    assert params["doc_id_field_key"] == "sourcepage"
    assert params["filterable_metadata_field_keys"] == {
        "sourcefile": "sourcefile",
        "sourcepage": "sourcepage",
        "category": "category",
    }
    assert params["searchable_fields"] == ["content", "filepath"]
    assert params["hybrid_search"] is True


def test_settings_are_updated():
    llm = object()
    embedding = FakeOpenAIEmbedding()

    module.initialize_index(
        **make_args(llm=llm, embed_model=embedding)
    )

    assert FakeSettings.llm is llm
    assert FakeSettings.embed_model is embedding


def test_index_is_bound_to_vector_store():
    index = module.initialize_index(**make_args())

    assert index.storage_context.vector_store is FakeVectorStore.instances[0]


def test_lifecycle_client_is_attached():
    index = module.initialize_index(**make_args())

    assert hasattr(index, "_azure_search_client")
    assert index._azure_search_client is FakeSearchIndexClient.instances[0]
    assert index._azure_search_aio is False


def test_async_lifecycle_client_is_attached():
    index = module.initialize_index(**make_args(aio=True))

    assert index._azure_search_client is FakeSearchClient.instances[0]
    assert index._azure_search_aio is True


@pytest.mark.asyncio
async def test_close_index_closes_async_client():
    index = module.initialize_index(**make_args(aio=True))

    await module.close_index(index)

    assert FakeSearchClient.instances[0].closed is True


@pytest.mark.asyncio
async def test_close_index_handles_missing_client():
    index = FakeVectorStoreIndex(None)

    await module.close_index(index)


@pytest.mark.asyncio
async def test_close_index_handles_sync_client():
    index = module.initialize_index(**make_args())

    await module.close_index(index)

    assert FakeSearchIndexClient.instances[0].closed is True


def test_no_legacy_gpt_vector_store_index():
    source = MODULE_PATH.read_text()

    assert "GPTVectorStoreIndex" not in source
    assert "from llama_index.core import ServiceContext" not in source
    assert "ServiceContext.from_defaults" not in source


def test_uses_current_vector_store_integration():
    source = MODULE_PATH.read_text()

    assert "llama_index.vector_stores.azureaisearch" in source
    assert "AzureAISearchVectorStore" in source


def test_uses_current_settings_api():
    source = MODULE_PATH.read_text()

    assert "from llama_index.core import Settings" in source
    assert "Settings.llm" in source
    assert "Settings.embed_model" in source


def test_does_not_silently_create_missing_index_by_default():
    source = MODULE_PATH.read_text()

    assert "IndexManagement.VALIDATE_INDEX" in source


def test_async_client_is_the_aio_sdk_client():
    source = MODULE_PATH.read_text()

    assert (
        "from azure.search.documents.aio import SearchClient as AsyncSearchClient"
        in source
    )


def test_no_unused_current_date_or_default_constants():
    source = MODULE_PATH.read_text()

    assert "CURRENT_DATE" not in source
    assert "DEFAULT_TOP_K" not in source
    assert "DEFAULT_TEMPERATURE" not in source
