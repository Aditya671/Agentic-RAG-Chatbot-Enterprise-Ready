# Runtime Correctness — Phase 4

This phase hardens the runtime boundary without changing the product's business behavior.

## Structured data

CSV analysis is exposed through `backend/orchestration/structured_query.py`. The maintained implementation uses pandas directly and separates LLM intent planning from deterministic, allow-listed dataframe operations. No generated Python is evaluated, and dataframe cell contents are never treated as executable instructions.

The async contract executes the deterministic query implementation in a worker thread so synchronous pandas work does not block the event loop.

## Azure AI Search

The Azure Search initializer remains responsible for binding an existing Search index to LlamaIndex. Its contract explicitly validates required inputs, defaults to existing-index validation, distinguishes sync and async SDK clients, and exposes an explicit `close_index()` lifecycle hook.

No Azure credentials or live Search resources are required by the contract tests.

## Test boundary

The Phase 4 tests focus on behavior that can be proven without cloud access:

- structured-query validation and async behavior;
- deterministic pandas aggregation/filtering;
- Azure Search initializer input validation;
- index-management defaults;
- lifecycle cleanup for sync and async Search clients;
- package/runtime compatibility contracts.

A successful local test run is **not** equivalent to Azure end-to-end validation. The latter remains a separate deployment-stage check because it requires real Azure resources and credentials.

## Current dependency strategy

Pandas is a first-class runtime dependency at `3.0.5`. The application no longer depends on a separate experimental LlamaIndex structured-query package. This removes the previous dependency conflict and eliminates an unnecessary arbitrary-code execution boundary.
