# Runtime correctness — Phase 10

## Provider-edge boundaries

Phase 10 separates application retrieval policy from LlamaIndex/Azure-specific
objects. `RetrievalConfig` remains provider-neutral; `provider_boundaries.py`
translates that policy only at the provider edge.

### Retrieval

`build_retriever()` validates and carries the configured top-k into the
provider retriever and resolves the application query-mode name to the
LlamaIndex `VectorStoreQueryMode` enum. Provider-specific options such as
rerank postprocessors can be supplied explicitly without changing the
application contract.

This makes the semantic-hybrid choice testable without Azure credentials and
prevents provider enums from leaking into higher-level policy code.

### Structured data

`build_structured_query_engine()` exposes the existing `StructuredQueryEngine`
adapter rather than allowing new application code to import
`PandasQueryEngine` directly. The experimental dependency therefore remains
isolated to one compatibility adapter.

The existing `IntegratedAsyncAgenticAiSystem` now exposes both provider-edge
factories while retaining the historical agent API. This is an incremental
migration seam: the large compatibility implementation is not duplicated.

## Validation

Provider-boundary tests use a fake index and a mocked structured-query engine.
They verify top-k propagation, semantic-hybrid mode translation, provider
option preservation, invalid-mode rejection, and structured-query dependency
isolation without Azure services or model credentials.
