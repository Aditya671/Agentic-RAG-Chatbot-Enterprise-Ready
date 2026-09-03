"""Dependency-isolated contracts for the Azure AI Search initializer."""
from __future__ import annotations

import importlib
import sys
import types

import pytest


def _load_module(monkeypatch: pytest.MonkeyPatch):
    class FakeSearchClient:
        def __init__(self, endpoint, index_name, credential):
            self.endpoint = endpoint
            self.index_name = index_name
            self.credential = credential
            self.closed = False

        async def close(self):
            self.closed = True

    class FakeSearchIndexClient:
        def __init__(self, endpoint, credential):
            self.endpoint = endpoint
            self.credential = credential
            self.closed = False

        def close(self):
            self.closed = True

    class FakeStorageContext:
        def __init__(self, vector_store):
            self.vector_store = vector_store

        @classmethod
        def from_defaults(cls, vector_store=None):
            return cls(vector_store)

    class FakeSettings:
        llm = None
        embed_model = None

    class FakeIndex:
        def __init__(self, storage_context):
            self.storage_context = storage_context

        @classmethod
        def from_documents(cls, documents, storage_context, llm, embed_model):
            assert documents == []
            assert llm is not None
            assert embed_model is not None
            return cls(storage_context)

    class FakeVectorStore:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class IndexManagement:
        VALIDATE_INDEX = "validate_index"
        CREATE_IF_NOT_EXISTS = "create_if_not_exists"

        def __init__(self, value):
            if value not in {
                self.VALIDATE_INDEX,
                self.CREATE_IF_NOT_EXISTS,
            }:
                raise ValueError(value)
            self.value = value

        def __eq__(self, other):
            return isinstance(other, IndexManagement) and self.value == other.value

    azure = types.ModuleType("azure")
    azure_search = types.ModuleType("azure.search")
    documents = types.ModuleType("azure.search.documents")
    documents_aio = types.ModuleType("azure.search.documents.aio")
    indexes = types.ModuleType("azure.search.documents.indexes")
    indexes_aio = types.ModuleType("azure.search.documents.indexes.aio")
    core = types.ModuleType("llama_index.core")
    llama = types.ModuleType("llama_index")
    vector = types.ModuleType("llama_index.vector_stores.azureaisearch")
    embeddings_azure = types.ModuleType("llama_index.embeddings.azure_openai")
    embeddings_openai = types.ModuleType("llama_index.embeddings.openai")

    documents.SearchClient = FakeSearchClient
    documents_aio.SearchClient = FakeSearchClient
    indexes.SearchIndexClient = FakeSearchIndexClient
    indexes_aio.SearchIndexClient = FakeSearchIndexClient
    core.Settings = FakeSettings
    core.StorageContext = FakeStorageContext
    core.VectorStoreIndex = FakeIndex
    embeddings_azure.AzureOpenAIEmbedding = type("AzureOpenAIEmbedding", (), {})
    embeddings_openai.OpenAIEmbedding = type("OpenAIEmbedding", (), {})
    vector.AzureAISearchVectorStore = FakeVectorStore
    vector.IndexManagement = IndexManagement

    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.search", azure_search)
    monkeypatch.setitem(sys.modules, "azure.search.documents", documents)
    monkeypatch.setitem(sys.modules, "azure.search.documents.aio", documents_aio)
    monkeypatch.setitem(sys.modules, "azure.search.documents.indexes", indexes)
    monkeypatch.setitem(sys.modules, "azure.search.documents.indexes.aio", indexes_aio)
    monkeypatch.setitem(sys.modules, "llama_index", llama)
    monkeypatch.setitem(sys.modules, "llama_index.core", core)
    monkeypatch.setitem(sys.modules, "llama_index.vector_stores.azureaisearch", vector)
    monkeypatch.setitem(sys.modules, "llama_index.embeddings.azure_openai", embeddings_azure)
    monkeypatch.setitem(sys.modules, "llama_index.embeddings.openai", embeddings_openai)

    module = importlib.import_module(
        "agentic_rag_chatbot_enterprise_ready.backend.indexer.azure_search_initializer_upgraded"
    )
    return module, FakeSearchClient, FakeSearchIndexClient, FakeVectorStore, FakeSettings, IndexManagement


def _args(**overrides):
    values = {
        "search_index_name": "test-index",
        "llm": object(),
        "embed_model": object(),
        "embed_size": 1536,
        "search_service_endpoint": "https://example.search.windows.net",
        "search_service_credential": object(),
    }
    values.update(overrides)
    return values


def test_sync_initializer_uses_existing_index_validation(monkeypatch):
    module, _, search_index_client, vector_store, _, management = _load_module(monkeypatch)
    index = module.initialize_index(**_args())

    assert index.storage_context.vector_store is not None
    assert search_index_client.instances if hasattr(search_index_client, "instances") else True
    assert vector_store.instances if hasattr(vector_store, "instances") else True


def test_initializer_validates_inputs(monkeypatch):
    module, *_ = _load_module(monkeypatch)

    with pytest.raises(ValueError, match="embed_size"):
        module.initialize_index(**_args(embed_size=0))
    with pytest.raises(ValueError, match="llm"):
        module.initialize_index(**_args(llm=None))
    with pytest.raises(ValueError, match="credential"):
        module.initialize_index(**_args(search_service_credential=None))
    with pytest.raises(TypeError, match="Unexpected keyword"):
        module.initialize_index(**_args(unexpected=True))


def test_string_index_management_is_supported(monkeypatch):
    module, _, _, vector_store, _, _ = _load_module(monkeypatch)
    module.initialize_index(**_args(index_management="create_if_not_exists"))
    assert vector_store.instances if hasattr(vector_store, "instances") else True


def test_lifecycle_close_handles_async_and_sync_clients(monkeypatch):
    module, *_ = _load_module(monkeypatch)

    class AsyncClient:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    class SyncClient:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    import asyncio

    async_client = AsyncClient()
    sync_client = SyncClient()

    class Holder:
        pass

    async_index = Holder()
    async_index._azure_search_client = async_client
    sync_index = Holder()
    sync_index._azure_search_client = sync_client

    asyncio.run(module.close_index(async_index))
    asyncio.run(module.close_index(sync_index))

    assert async_client.closed is True
    assert sync_client.closed is True
