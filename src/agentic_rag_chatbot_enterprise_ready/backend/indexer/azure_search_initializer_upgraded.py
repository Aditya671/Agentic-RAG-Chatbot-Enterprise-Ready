"""Azure AI Search + LlamaIndex vector-index initialization.

This module intentionally focuses on *connecting to an existing* Azure AI
Search index and exposing it through LlamaIndex's AzureAISearchVectorStore.

The implementation targets the current LlamaIndex 0.14.x architecture:
- ``llama-index-core`` uses ``Settings`` rather than the removed ServiceContext.
- Azure AI Search is supplied through the dedicated
  ``llama-index-vector-stores-azureaisearch`` integration.
- The Azure SDK supports both synchronous and asynchronous clients.

No event-loop patching is performed here. Application code should own its
asyncio lifecycle.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Union

from azure.search.documents import SearchClient
from azure.search.documents.aio import SearchClient as AsyncSearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.aio import (
    SearchIndexClient as AsyncSearchIndexClient,
)
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.azureaisearch import (
    AzureAISearchVectorStore,
    IndexManagement,
)

logger = logging.getLogger(__name__)

EmbeddingModel = Union[AzureOpenAIEmbedding, OpenAIEmbedding]


def _build_field_params(
    *,
    embed_size: int,
    old_index: bool,
) -> dict[str, Any]:
    """Build the field mapping for the two supported index schemas."""
    if embed_size <= 0:
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
        params.update(
            {
                "chunk_field_key": "chunk",
                "doc_id_field_key": "doc_id",
            }
        )

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
    """Create the appropriate Azure AI Search client and vector store.

    Returns both objects so the caller can explicitly close the Azure client.
    """
    if not search_index_name.strip():
        raise ValueError("search_index_name must be a non-empty string.")
    if not search_service_endpoint.strip():
        raise ValueError("search_service_endpoint must be a non-empty string.")
    if search_service_credential is None:
        raise ValueError("search_service_credential is required.")

    field_params = _build_field_params(
        embed_size=embed_size,
        old_index=old_index,
    )

    if aio:
        # The current LlamaIndex Azure AI Search integration accepts an async
        # SearchClient/SearchIndexClient directly. For existing-index usage,
        # SearchClient is the least-privileged client.
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
        # Sync path uses SearchIndexClient so the vector-store integration can
        # validate/create an index when requested.
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
    """Initialize a LlamaIndex backed by an existing Azure AI Search index.

    Parameters
    ----------
    search_index_name:
        Existing Azure AI Search index name.
    llm:
        Pre-configured LlamaIndex LLM. It is also assigned to
        ``Settings.llm`` for compatibility with the rest of the application.
    embed_model:
        Pre-configured embedding model.
    embed_size:
        Exact vector dimensionality of ``embed_model``. This must match the
        Azure AI Search vector field dimension.
    search_service_endpoint:
        Azure AI Search endpoint.
    search_service_credential:
        AzureKeyCredential or Microsoft Entra token credential.
    use_azure:
        Retained for backwards compatibility. The embedding/provider is already
        supplied through ``embed_model``; therefore this flag does not change
        client construction.
    **kwargs:
        ``aio`` (bool):
            Use Azure's async SearchClient.
        ``old_index`` (bool):
            Use the legacy ``content/sourcepage`` schema and hybrid settings.
        ``index_management`` (IndexManagement | str):
            Defaults to ``VALIDATE_INDEX`` because this function initializes an
            existing index. Use ``CREATE_IF_NOT_EXISTS`` only when an index may
            legitimately be created by this layer.

    Returns
    -------
    VectorStoreIndex
        Empty LlamaIndex bound to the configured Azure AI Search vector store.

    Notes
    -----
    The returned object owns the vector-store client. Call
    ``await close_index(index)`` when using the async path.
    """
    del use_azure  # Compatibility parameter; embed_model determines the provider.

    aio = bool(kwargs.pop("aio", False))
    old_index = bool(kwargs.pop("old_index", False))
    index_management = kwargs.pop(
        "index_management",
        IndexManagement.VALIDATE_INDEX,
    )

    if isinstance(index_management, str):
        try:
            index_management = IndexManagement(index_management)
        except ValueError as exc:
            valid = ", ".join(
                [
                    IndexManagement.VALIDATE_INDEX.value,
                    IndexManagement.CREATE_IF_NOT_EXISTS.value,
                ]
            )
            raise ValueError(
                f"Unsupported index_management={index_management!r}. "
                f"Expected one of: {valid}"
            ) from exc

    if not isinstance(index_management, IndexManagement):
        raise TypeError(
            "index_management must be an IndexManagement value or its string value."
        )

    if kwargs:
        unexpected = ", ".join(sorted(kwargs))
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

    # Preserve the application's existing global Settings contract while also
    # passing the models explicitly to the index.
    Settings.llm = llm
    Settings.embed_model = embed_model

    index = VectorStoreIndex.from_documents(
        [],
        storage_context=storage_context,
        llm=llm,
        embed_model=embed_model,
    )

    # Attach the client for an explicit lifecycle API without changing the
    # LlamaIndex object model.
    setattr(index, "_azure_search_client", client)
    setattr(index, "_azure_search_aio", aio)

    logger.info(
        "Initialized Azure AI Search vector index '%s' (aio=%s, old_index=%s, "
        "index_management=%s)",
        search_index_name,
        aio,
        old_index,
        index_management.value,
    )
    return index


async def close_index(index: VectorStoreIndex) -> None:
    """Close the Azure AI Search client owned by ``initialize_index``.

    Safe to call on indexes created by older versions that do not have the
    private lifecycle attributes.
    """
    client = getattr(index, "_azure_search_client", None)
    if client is None:
        return

    close = getattr(client, "close", None)
    if close is None:
        return

    result = close()
    if hasattr(result, "__await__"):
        await result
