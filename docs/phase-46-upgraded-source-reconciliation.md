# Phase 46 — Historical upgraded-source reconciliation

Status: ready for review.

## Why this phase exists

The repository previously treated the `_upgraded.py` suffix as sufficient evidence that a module was a duplicate. That was too aggressive. The August 2026 enterprise-upgrade commit contains enhanced implementations with additional validation, lifecycle handling, security hardening, compatibility logic, and regression tests. This phase reopens those historical sources and compares them with the current runtime before deciding whether each enhancement belongs in the maintained path.

## Reconciliation policy

For every historical upgraded implementation:

1. compare it with the current runtime and related callers;
2. recover enhancements that were lost or bypassed;
3. preserve later architectural decisions that intentionally retired a capability;
4. keep public import compatibility where required;
5. add deterministic regression coverage before considering the boundary complete.

A module is not accepted merely because it is called `*_upgraded.py`, and it is not rejected merely because it has that suffix.

## Reconciled in this phase

### Cosmos DB data layer

Historical enhanced implementation restored to the maintained module.

Recovered behavior includes:

- parameterized Cosmos SQL instead of interpolated values;
- partition-key-aware reads and deletes;
- non-mutating cleanup of Cosmos metadata;
- async isolation of the synchronous Cosmos SDK with `asyncio.to_thread`;
- correct existing-user handling;
- current Chainlit data-layer methods including `get_favorite_steps`;
- soft/hard thread deletion semantics;
- idempotent lifecycle `close()` handling;
- injectable client for deterministic tests.

### MongoDB data layer

Historical enhanced implementation restored to the maintained module.

Recovered behavior includes:

- PyMongo `AsyncMongoClient` instead of the older Motor implementation;
- input validation and connection-pool configuration;
- deterministic UTC timestamps;
- safe document conversion without mutating Mongo results;
- cursor-based pagination;
- required Chainlit lifecycle methods;
- unique user/feedback indexes;
- async shutdown through `close()`.

### Uploaded file wrapper

The historical enhanced contract was reconciled rather than copied blindly. The maintained wrapper now supports both:

- explicit in-memory upload payloads; and
- file-backed reads.

It also preserves the historical public attributes and avoids exposing file bytes through `repr()`.

### LlamaIndex ingestion compatibility

The enhanced ingestion implementation remains the underlying runtime implementation. A missing public `upsert_documents_to_index` helper was identified because the PDF compatibility surface imported it but the enhanced implementation did not expose it. The helper is now restored at the stable public boundary using the current `StorageContext`/`VectorStoreIndex` path.

## Previously reconciled and retained

The following historical enhanced areas were reviewed and remain represented by the current runtime architecture rather than being reverted to their old module layout:

- Agent orchestration and response normalization
- LLM loading and embedding configuration
- model registry/capability metadata
- reranking
- property-graph RAG
- Azure credential management
- AWS credential management
- Azure AI Search index initialization
- Azure Search index engine
- PDF compatibility surface
- user-upload indexing
- Celery indexing task
- Chainlit frontend/runtime integration

These areas already received later canonicalization work. This phase does not overwrite those later improvements with older historical snapshots.

## Intentionally not restored

### Code interpreter / E2B

The historical enhanced code interpreter was deliberately retired by a later security refactor that removed remote code execution from the maintained runtime. Reintroducing that implementation would contradict the current security boundary.

### PandasAI execution surface

The historical PandasAI implementation was deliberately removed because it was an obsolete execution surface. It is not restored merely because an older upgraded implementation exists.

## Verification boundary

The regression suite in this phase focuses on deterministic behavior and compatibility boundaries. It does not claim live Azure Cosmos, MongoDB, Azure AI Search, Blob Storage, or Chainlit cloud integration against the user's infrastructure.

The CI quality workflow remains the authoritative repository gate for compilation, linting, tests, and package build. Live cloud integration should be exercised separately in an environment with the required credentials and services.

## Remaining known dependency

Celery retry/redelivery remains disabled until the persisted vector/summary indexing path has a proven artifact-level idempotency contract under partial failure and concurrent execution.
