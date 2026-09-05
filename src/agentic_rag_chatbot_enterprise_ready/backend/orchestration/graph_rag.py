"""Canonical property-graph RAG runtime.

The historical ``graph_rag`` import path is preserved, but the implementation
uses LlamaIndex's current PropertyGraphIndex architecture. Graph storage and
vector retrieval are explicit dependencies so the runtime does not silently
fall back from a configured persistent graph to ephemeral storage.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from typing import Any

from llama_index.core import Document, PropertyGraphIndex
from llama_index.core.graph_stores import SimplePropertyGraphStore
from llama_index.core.llms import LLM
from llama_index.core.vector_stores.simple import SimpleVectorStore

try:
    from llama_index.graph_stores.nebula import NebulaPropertyGraphStore
except ImportError:  # pragma: no cover - optional integration
    NebulaPropertyGraphStore = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class GraphRAGError(RuntimeError):
    """Base exception for GraphRAG failures."""


class GraphRAGConfigurationError(GraphRAGError):
    """Raised when GraphRAG configuration is invalid."""


class GraphRAGSystem:
    """Property-graph RAG system with optional persistent NebulaGraph storage.

    ``PropertyGraphIndex`` coordinates graph topology and semantic retrieval.
    A separate vector store is therefore injectable because the Nebula
    property-graph integration does not provide native vector queries.
    ``SimpleVectorStore`` remains the compatibility default; production
    deployments should inject durable vector storage when graph embeddings
    must survive process restarts.
    """

    def __init__(
        self,
        llm: LLM,
        embed_model: Any,
        *,
        graph_store: Any | None = None,
        vector_store: Any | None = None,
        use_nebula: bool | None = None,
        nebula_space_name: str | None = None,
        nebula_url: str | None = None,
        nebula_port: int | None = None,
        nebula_username: str | None = None,
        nebula_password: str | None = None,
        show_progress: bool = False,
        similarity_top_k: int = 5,
        path_depth: int = 1,
        include_text: bool = True,
        embed_kg_nodes: bool = True,
    ) -> None:
        if llm is None:
            raise GraphRAGConfigurationError("llm is required.")
        if embed_model is None:
            raise GraphRAGConfigurationError("embed_model is required.")
        if isinstance(similarity_top_k, bool) or not isinstance(similarity_top_k, int) or similarity_top_k < 1:
            raise ValueError("similarity_top_k must be a positive integer.")
        if isinstance(path_depth, bool) or not isinstance(path_depth, int) or path_depth < 0:
            raise ValueError("path_depth must be a non-negative integer.")

        self.llm = llm
        self.embed_model = embed_model
        self.show_progress = bool(show_progress)
        self.similarity_top_k = similarity_top_k
        self.path_depth = path_depth
        self.include_text = bool(include_text)
        self.embed_kg_nodes = bool(embed_kg_nodes)

        self.graph_store = graph_store or self._build_graph_store(
            use_nebula=use_nebula,
            space_name=nebula_space_name,
            url=nebula_url,
            port=nebula_port,
            username=nebula_username,
            password=nebula_password,
        )
        self.vector_store = vector_store or SimpleVectorStore()
        self.index: PropertyGraphIndex | None = None

        logger.info(
            "GraphRAGSystem initialized with graph_store=%s, vector_store=%s",
            type(self.graph_store).__name__,
            type(self.vector_store).__name__,
        )

    @staticmethod
    def _build_graph_store(
        *,
        use_nebula: bool | None,
        space_name: str | None,
        url: str | None,
        port: int | None,
        username: str | None,
        password: str | None,
    ) -> Any:
        configured_space = space_name or os.getenv("NEBULA_SPACE_NAME") or os.getenv("NEBULA_SPACE")

        if use_nebula is None:
            use_nebula = bool(configured_space)

        if not use_nebula:
            logger.info("Using SimplePropertyGraphStore for GraphRAG.")
            return SimplePropertyGraphStore()

        if NebulaPropertyGraphStore is None:
            raise GraphRAGConfigurationError(
                "Nebula GraphRAG was requested but 'llama-index-graph-stores-nebula' is not installed."
            )
        if not configured_space:
            raise GraphRAGConfigurationError(
                "NEBULA_SPACE_NAME/NEBULA_SPACE is required when NebulaGraph is enabled."
            )

        kwargs: dict[str, Any] = {"space": configured_space}
        configured_url = url or os.getenv("NEBULA_URL")
        if configured_url:
            kwargs["url"] = configured_url

        configured_port = port if port is not None else os.getenv("NEBULA_PORT")
        if configured_port is not None:
            try:
                kwargs["port"] = int(configured_port)
            except (TypeError, ValueError) as exc:
                raise GraphRAGConfigurationError("NEBULA_PORT must be an integer.") from exc

        configured_username = username or os.getenv("NEBULA_USERNAME")
        if configured_username:
            kwargs["username"] = configured_username
        configured_password = password or os.getenv("NEBULA_PASSWORD")
        if configured_password:
            kwargs["password"] = configured_password

        try:
            store = NebulaPropertyGraphStore(**kwargs)
            logger.info("Using persistent NebulaPropertyGraphStore for space '%s'.", configured_space)
            return store
        except Exception as exc:
            logger.exception("Failed to initialize NebulaPropertyGraphStore.")
            raise GraphRAGConfigurationError(
                "Failed to initialize the configured NebulaGraph store."
            ) from exc

    @staticmethod
    def _validate_documents(documents: Sequence[Document]) -> list[Document]:
        if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes, bytearray)):
            raise TypeError("documents must be a sequence of LlamaIndex Document objects.")

        validated: list[Document] = []
        for document in documents:
            if not isinstance(document, Document):
                raise TypeError("All graph documents must be LlamaIndex Document objects.")
            if not getattr(document, "text", "").strip():
                logger.warning("Skipping empty graph document.")
                continue
            validated.append(document)
        return validated

    def build_graph_from_documents(
        self,
        documents: Sequence[Document],
        *,
        kg_extractors: Sequence[Any] | None = None,
        max_triplets_per_chunk: int | None = None,
    ) -> PropertyGraphIndex | None:
        """Build or extend the property graph from documents."""
        validated = self._validate_documents(documents)
        if not validated:
            logger.warning("No non-empty documents supplied; graph build skipped.")
            return self.index

        kwargs: dict[str, Any] = {
            "property_graph_store": self.graph_store,
            "vector_store": self.vector_store,
            "embed_model": self.embed_model,
            "embed_kg_nodes": self.embed_kg_nodes,
            "show_progress": self.show_progress,
        }
        if kg_extractors:
            kwargs["kg_extractors"] = list(kg_extractors)
        if max_triplets_per_chunk is not None:
            logger.warning(
                "max_triplets_per_chunk=%s is ignored by PropertyGraphIndex; configure extraction through kg_extractors instead.",
                max_triplets_per_chunk,
            )

        try:
            if self.index is None:
                self.index = PropertyGraphIndex.from_documents(validated, **kwargs)
            else:
                for document in validated:
                    self.index.insert(document)
            logger.info("Property graph built/updated successfully from %d documents.", len(validated))
            return self.index
        except Exception as exc:
            logger.exception("Failed to build/update property graph.")
            raise GraphRAGError("Failed to build/update the knowledge graph.") from exc

    def insert_documents(self, documents: Sequence[Document]) -> PropertyGraphIndex | None:
        """Insert additional documents into an existing property graph."""
        validated = self._validate_documents(documents)
        if not validated:
            return self.index
        if self.index is None:
            return self.build_graph_from_documents(validated)
        try:
            for document in validated:
                self.index.insert(document)
            return self.index
        except Exception as exc:
            logger.exception("Failed to insert documents into property graph.")
            raise GraphRAGError("Failed to insert documents into the knowledge graph.") from exc

    def load_existing_graph(
        self,
        *,
        graph_store: Any | None = None,
        vector_store: Any | None = None,
    ) -> PropertyGraphIndex:
        """Attach the RAG layer to an already-populated property graph."""
        if graph_store is not None:
            self.graph_store = graph_store
        if vector_store is not None:
            self.vector_store = vector_store
        try:
            self.index = PropertyGraphIndex.from_existing(
                property_graph_store=self.graph_store,
                vector_store=self.vector_store,
                embed_model=self.embed_model,
                embed_kg_nodes=self.embed_kg_nodes,
            )
            logger.info("Loaded existing property graph successfully.")
            return self.index
        except Exception as exc:
            logger.exception("Failed to load existing property graph.")
            raise GraphRAGError("Failed to load the existing knowledge graph.") from exc

    def as_retriever(self) -> Any:
        """Return the default property-graph retriever."""
        if self.index is None:
            raise GraphRAGError("Graph index is not built. Build or load a graph before retrieving.")
        return self.index.as_retriever(
            include_text=self.include_text,
            similarity_top_k=self.similarity_top_k,
            path_depth=self.path_depth,
        )

    def as_query_engine(self) -> Any:
        """Return a query engine over the property graph."""
        if self.index is None:
            raise GraphRAGError("Graph index is not built. Build or load a graph before querying.")
        return self.index.as_query_engine(
            include_text=self.include_text,
            similarity_top_k=self.similarity_top_k,
            path_depth=self.path_depth,
        )

    def query(self, query_text: str) -> str:
        """Query the graph and normalize the result to the agent-tool contract."""
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("query_text must be a non-empty string.")
        try:
            response = self.as_query_engine().query(query_text)
            return str(response)
        except GraphRAGError:
            raise
        except Exception as exc:
            logger.exception("GraphRAG query failed.")
            raise GraphRAGError("Knowledge graph query failed.") from exc

    def close(self) -> None:
        """Release graph/vector resources when their integrations support it."""
        for resource in (self.graph_store, self.vector_store):
            close = getattr(resource, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    logger.exception("Failed to close GraphRAG resource %s.", type(resource).__name__)

    def __enter__(self) -> GraphRAGSystem:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


__all__ = ["GraphRAGConfigurationError", "GraphRAGError", "GraphRAGSystem"]
