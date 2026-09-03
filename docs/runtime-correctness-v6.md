# Runtime Correctness — Phase 6

## Agent retrieval contract

Phase 6 makes retrieval policy explicit at the orchestration boundary. The
runtime currently retrieves through LlamaIndex over Azure AI Search, using
semantic-hybrid search and a configurable similarity `top_k`. The new
`RetrievalConfig` captures those two policy values without importing Azure,
LlamaIndex, or any other runtime dependency.

### Contract

- `top_k` must be an integer greater than or equal to 1.
- Boolean values are rejected even though Python treats `bool` as an `int`.
- `query_mode` must be a non-empty string.
- The configuration is immutable after construction.
- `as_kwargs()` exposes the provider-facing names used by LlamaIndex:
  `similarity_top_k` and `vector_store_query_mode`.
- The default remains `top_k=5` with `semantic_hybrid`, matching the existing
  agent behaviour.

## Why this boundary exists

Retrieval behaviour is an application contract, not merely an SDK detail. By
keeping the policy dependency-free, contract tests can verify propagation and
validation without Azure credentials, a live search index, or an LLM call.
Provider-specific integration remains at the runtime boundary.

## Validation strategy

The Phase 6 tests cover:

1. current default retrieval behaviour;
2. custom `top_k` propagation;
3. invalid `top_k` values, including booleans;
4. invalid query modes; and
5. immutability of the retrieval policy.

These tests intentionally do not claim live Azure retrieval coverage. A live
smoke test should remain a deployment/integration concern where the required
Azure project, search index, credentials, and embedding configuration exist.
