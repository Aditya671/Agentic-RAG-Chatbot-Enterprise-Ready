# Runtime Correctness — Phase 23

## Canonical GraphRAG surface

Phase 23 removes the duplicate GraphRAG implementation and makes
`backend.orchestration.graph_rag` the maintained runtime surface.

### Architecture

The canonical implementation now uses:

- `PropertyGraphIndex` instead of deprecated `KnowledgeGraphIndex`.
- `SimplePropertyGraphStore` for the explicit in-memory compatibility mode.
- Optional `NebulaPropertyGraphStore` when Nebula is deliberately configured.
- An injectable vector store, with `SimpleVectorStore` as the compatibility default.

Graph storage and vector retrieval remain separate concerns. A configured
NebulaGraph failure is surfaced as a configuration error rather than silently
switching a persistent deployment to ephemeral storage.

### Runtime lifecycle

The canonical component supports:

- initial graph construction with `build_graph_from_documents()`;
- incremental insertion with `insert_documents()`;
- attaching to an existing graph with `load_existing_graph()`;
- graph retrieval and query engines through explicit settings;
- stable `GraphRAGError` and `GraphRAGConfigurationError` failures;
- resource cleanup through `close()` and context-manager support.

The legacy `max_triplets_per_chunk` argument is accepted only for compatibility
and is not forwarded to the property-graph API. Extraction policy belongs in
configured graph extractors.

### Compatibility boundary

`graph_rag_upgraded.py` is now only a re-export of the canonical implementation.
It no longer contains an independent runtime implementation.

The migration-era GraphRAG test was moved into `tests/test_graph_rag.py` and its
hard-coded `/mnt/data` dependency was removed. The obsolete upgrade report was
also removed so the repository does not retain a second narrative around the
old implementation.

### Verification boundary

The maintained regression suite uses dependency-isolated provider stubs. It
covers configuration, document validation, graph construction, incremental
insertion, existing-graph loading, retrieval/query configuration, error
translation, and lifecycle cleanup.

Live NebulaGraph, durable vector-store, ingestion-scale, concurrent access,
and answer-quality validation remain deployment/integration concerns and are
not claimed as local test coverage.
