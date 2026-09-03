# Runtime Correctness — Phase 4

This phase hardens the runtime boundary without changing the product's business behavior.

## Structured data

CSV analysis is exposed through `backend/orchestration/structured_query.py` rather than letting the agent depend directly on the experimental Pandas query implementation. The adapter currently delegates to the existing `PandasQueryEngine`, preserving behavior while giving the application a replaceable seam.

The async contract deliberately executes the synchronous query implementation in a worker thread. This avoids assuming that the experimental dependency exposes a stable `aquery()` API across releases.

## Azure AI Search

The Azure Search initializer remains responsible for binding an existing Search index to LlamaIndex. Its contract now explicitly validates required inputs, defaults to existing-index validation, distinguishes sync and async SDK clients, and exposes an explicit `close_index()` lifecycle hook.

No Azure credentials or live Search resources are required by the contract tests.

## Test boundary

The Phase 4 tests focus on behavior that can be proven without cloud access:

- structured-query validation and async behavior;
- Azure Search initializer input validation;
- index-management defaults;
- lifecycle cleanup for sync and async Search clients;
- package/runtime compatibility contracts.

A successful local test run is **not** equivalent to Azure end-to-end validation. The latter remains a separate deployment-stage check because it requires real Azure resources and credentials.

## Replacement strategy

`llama-index-experimental` remains in the dependency set for now because the application still relies on its Pandas query behavior. The dependency is intentionally isolated so a supported replacement can be introduced without rewriting the agent orchestration layer.
