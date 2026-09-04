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

`build_structured_query_engine()` exposes the maintained `StructuredQueryEngine`
implementation. It uses pandas for deterministic dataframe execution and an
LLM only to produce a validated JSON operation plan. No generated Python is
evaluated and no experimental LlamaIndex query package is required.

The `IntegratedAsyncAgenticAiSystem` retains the historical agent API while the
structured-data provider boundary remains independently testable.

## Validation

Provider-boundary tests use a fake index and an in-memory pandas dataframe.
They verify top-k propagation, semantic-hybrid mode translation, provider
option preservation, invalid-mode rejection, native structured-query
construction, and deterministic execution without Azure services or model
credentials.
