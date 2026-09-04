"""Canonical Azure AI Search + LlamaIndex index initialization.

This module owns the maintained Azure Search integration. The historical
``index_engine_upgraded`` path is retired rather than used as a second runtime
implementation.

The implementation uses current LlamaIndex 0.14.x APIs, explicit Azure SDK
clients, caller-owned credentials, and an explicit client lifecycle. It does
not patch asyncio or create credentials at import time.
"""
from __future__ import annotations

import logging
from typing import Any, Union

from azure.search.documents.aio import SearchClient as AsyncSearchClient
from azure.search.documents.indexes import SearchIndexClient
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.azureaisearch import AzureAISearchVectorStore, IndexManagement

logger = logging.getLogger(__name__)
EmbeddingModel = Union[AzureOpenAIEmbedding, OpenAIEmbedding]


def _build_field_params(*, embed_size: int, old_index: bool) -> dict[str, Any]:
    """Build field mapping for the current or legacy Azure Search schema."""
    if isinstance(embed_size, bool) or not isinstance(embed_size, int) or embed_size <= 0:
        raise ValueError("embed_size must be a positive integer.")

    params: dict[str, Any] = {
        "id_field_key": "id",
        "embedding_field_key": "embedding",
        "embedding_dimensionality": embed_size,
        "metadata_string_field_key": "metadata",
        "language_analyzer": "en.lucene",
        "vector_algorithm_type": "exhaustiveKnn",
    }
    if old_index:
        params.update(
            {
                "chunk_field_key": "content",
                "doc_id_field_key": "sourcepage",
                "filterable_metadata_field_keys": {
                    "sourcefile": "sourcefile",
                    "sourcepage": "sourcepage",
                    "category": "category",
                },
                "searchable_fields": ["content", "filepath"],
                "hybrid_search": True,
            }
        )
    else:
        params.update({"chunk_field_key": "chunk", "doc_id_field_key": "doc_id"})
    return params


def _build_vector_store(
    *,
    search_index_name: str,
    embed_size: int,
    search_service_endpoint: str,
    search_service_credential: Any,
    aio: bool,
    old_index: bool,
    index_management: IndexManagement,
) -> tuple[AzureAISearchVectorStore, Any]:
    """Create the Azure Search client and LlamaIndex vector-store boundary."""
    if not isinstance(search_index_name, str) or not search_index_name.strip():
        raise ValueError("search_index_name must be a non-empty string.")
    if not isinstance(search_service_endpoint, str) or not search_service_endpoint.strip():
        raise ValueError("search_service_endpoint must be a non-empty string.")
    if search_service_credential is None:
        raise ValueError("search_service_credential is required.")

    field_params = _build_field_params(embed_size=embed_size, old_index=old_index)
    if aio:
        client = AsyncSearchClient(
            endpoint=search_service_endpoint,
            index_name=search_index_name,
            credential=search_service_credential,
        )
        vector_store = AzureAISearchVectorStore(
            search_or_index_client=client,
            index_name=None,
            index_management=index_management,
            **field_params,
        )
    else:
        client = SearchIndexClient(
            endpoint=search_service_endpoint,
            credential=search_service_credential,
        )
        vector_store = AzureAISearchVectorStore(
            search_or_index_client=client,
            index_name=search_index_name,
            index_management=index_management,
            **field_params,
        )
    return vector_store, client


def initialize_index(
    search_index_name: str,
    llm: Any,
    embed_model: EmbeddingModel,
    embed_size: int,
    search_service_endpoint: str,
    search_service_credential: Any,
    use_azure: bool = True,
    **kwargs: Any,
) -> VectorStoreIndex:
    """Initialize an empty LlamaIndex bound to Azure AI Search."""
    del use_azure
    aio = bool(kwargs.pop("aio", False))
    old_index = bool(kwargs.pop("old_index", False))
    index_management = kwargs.pop("index_management", IndexManagement.VALIDATE_INDEX)

    if isinstance(index_management, str):
        try:
            index_management = IndexManagement(index_management)
        except ValueError as exc:
            valid_values = (
                str(IndexManagement.VALIDATE_INDEX.value),
                str(IndexManagement.CREATE_IF_NOT_EXISTS.value),
            )
            valid = ", ".join(valid_values)
            raise ValueError(
                f"Unsupported index_management={index_management!r}. Expected one of: {valid}"
            ) from exc
    if not isinstance(index_management, IndexManagement):
        raise TypeError("index_management must be an IndexManagement value or its string value.")
    if kwargs:
        unexpected = ", ".join(str(key) for key in sorted(kwargs))
        raise TypeError(f"Unexpected keyword argument(s): {unexpected}")
    if llm is None:
        raise ValueError("llm must be provided.")
    if embed_model is None:
        raise ValueError("embed_model must be provided.")

    vector_store, client = _build_vector_store(
        search_index_name=search_index_name,
        embed_size=embed_size,
        search_service_endpoint=search_service_endpoint,
        search_service_credential=search_service_credential,
        aio=aio,
        old_index=old_index,
        index_management=index_management,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    Settings.llm = llm
    Settings.embed_model = embed_model
    index = VectorStoreIndex.from_documents(
        [], storage_context=storage_context, llm=llm, embed_model=embed_model
    )
    setattr(index, "_azure_search_client", client)
    setattr(index, "_azure_search_aio", aio)
    logger.info(
        "Initialized Azure AI Search vector index '%s' (aio=%s, old_index=%s, index_management=%s)",
        search_index_name,
        aio,
        old_index,
        index_management.value,
    )
    return index


async def close_index(index: VectorStoreIndex) -> None:
    """Close the Azure Search client owned by an initialized index."""
    client = getattr(index, "_azure_search_client", None)
    if client is None:
        return
    close = getattr(client, "close", None)
    if close is None:
        return
    result = close()
    if hasattr(result, "__await__"):
        await result


__all__ = ["EmbeddingModel", "initialize_index", "close_index"]
