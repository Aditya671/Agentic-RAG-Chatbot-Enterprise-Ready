"""Dependency-light tests for ingestion invariants."""
from __future__ import annotations

import importlib
import sys
import types

import pandas as pd
import pytest


@pytest.fixture
def indexer(monkeypatch):
    """Load the canonical indexer with only the required external symbols stubbed."""
    llama_core = types.ModuleType("llama_index.core")
    llama_schema = types.ModuleType("llama_index.core.schema")
    azure_cred = types.ModuleType("azure.core.credentials")
    azure_search = types.ModuleType("azure.search.documents.indexes")
    llama_embed = types.ModuleType("llama_index.embeddings.azure_openai")
    llama_vector = types.ModuleType("llama_index.vector_stores.azureaisearch")

    class FakeDocument:
        def __init__(self, text, metadata, id_=None):
            self.text = text
            self.metadata = metadata
            self.id_ = id_

    llama_schema.Document = FakeDocument
    llama_core.Settings = types.SimpleNamespace()
    llama_core.StorageContext = object
    llama_core.VectorStoreIndex = object
    azure_cred.AzureKeyCredential = object
    azure_search.SearchIndexClient = object
    llama_embed.AzureOpenAIEmbedding = object
    llama_vector.AzureAISearchVectorStore = object
    llama_vector.IndexManagement = types.SimpleNamespace(CREATE_IF_NOT_EXISTS="create_if_not_exists")

    modules = {
        "llama_index": types.ModuleType("llama_index"),
        "llama_index.core": llama_core,
        "llama_index.core.schema": llama_schema,
        "azure": types.ModuleType("azure"),
        "azure.core": types.ModuleType("azure.core"),
        "azure.core.credentials": azure_cred,
        "azure.search": types.ModuleType("azure.search"),
        "azure.search.documents": types.ModuleType("azure.search.documents"),
        "azure.search.documents.indexes": azure_search,
        "llama_index.embeddings": types.ModuleType("llama_index.embeddings"),
        "llama_index.embeddings.azure_openai": llama_embed,
        "llama_index.vector_stores": types.ModuleType("llama_index.vector_stores"),
        "llama_index.vector_stores.azureaisearch": llama_vector,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    module_name = "agentic_rag_chatbot_enterprise_ready.backend.indexer.llama_indexer_upgraded"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_chunking_is_deterministic_and_overlapping(indexer):
    chunks = indexer.chunk_text_simple("abcdefghij", chunk_size=6, overlap=2)
    assert chunks == [
        ("abcdef", 0, 6),
        ("efghij", 4, 10),
    ]


def test_chunking_rejects_invalid_invariants(indexer):
    with pytest.raises(ValueError, match="smaller than chunk_size"):
        indexer.chunk_text_simple("abc", chunk_size=3, overlap=3)
    with pytest.raises(ValueError, match="greater than zero"):
        indexer.chunk_text_simple("abc", chunk_size=0, overlap=0)


def test_document_ids_are_stable(indexer):
    assert indexer.make_doc_id("same-source") == indexer.make_doc_id("same-source")
    assert indexer.make_doc_id("same-source") != indexer.make_doc_id("other-source")


def test_dataframe_extraction_validates_columns_and_row_limit(indexer):
    frame = pd.DataFrame({"name": ["a", "b", "c"], "value": [1, 2, 3]})
    text, _ = indexer.extract_text_from_dataframe(
        frame,
        text_columns=["name", "value"],
        max_rows=2,
    )
    assert text.splitlines() == ["name,value", "a,1", "b,2"]

    with pytest.raises(ValueError, match="Unknown DataFrame columns"):
        indexer.extract_text_from_dataframe(frame, text_columns=["missing"])


def test_supported_extensions_are_explicit(indexer):
    assert indexer.SUPPORTED_EXTENSIONS == {".pdf", ".docx", ".txt", ".md", ".csv"}
