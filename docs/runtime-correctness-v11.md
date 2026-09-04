# Runtime correctness — Phase 11

## Orchestration convergence

Phase 10 established provider-edge factories. Phase 11 makes those seams part of
an actual agent construction path instead of leaving them as optional helpers.

### Retrieval policy

`IntegratedAsyncAgenticAiSystem` now rebuilds its runtime agent through
`agent_builder.build_agent()`. The builder consumes `AgentRuntimeBoundary`'s
`RetrievalConfig` and delegates provider translation to `build_retriever()`.
The integrated path therefore no longer chooses `VectorStoreQueryMode` itself.

Configuration setters that can change retrieval, model, index, or optional
agent capabilities resynchronize the runtime boundary and rebuild the
converged agent. This keeps the configured `top_k` and query mode aligned with
the actual provider retriever after runtime changes.

### Structured CSV querying

The integrated runtime now rebuilds its CSV engine through
`build_structured_query_engine()` and the stable `StructuredQueryEngine`
adapter. Existing prompt construction and metadata enrichment are preserved;
only the provider construction boundary changes.

The original compatibility implementation remains available. This is an
incremental convergence step: the integrated class is the migration path while
legacy consumers continue to use the historical API.

## Validation

The Phase 11 tests exercise the converged agent builder without Azure services
or model credentials. They verify that application retrieval policy reaches the
provider factory, reranker configuration remains explicit, and optional graph,
code, and CSV tools remain part of the constructed tool set.
