# Phase 73 — Background Processing & Idempotency

## Purpose

Phase 73 hardens the maintained asynchronous document-indexing path without introducing a second indexing implementation.

The boundary is:

```text
uploaded artifact
      ↓
stable artifact identity
      ↓
Celery task identity
      ↓
background indexing
      ↓
existing hash/version-aware indexer
      ↓
indexed / unchanged / failed outcome
```

The phase establishes the identity and failure contracts needed before automatic Celery retries can safely be enabled.

## Existing implementation retained

The canonical implementation remains:

`backend.tasks.index_files_task → UserUploadedFileIndexer.index_uploaded_files()`

The existing indexer already compares persisted file hash, normalized path, and index version before deciding whether a file needs indexing. Phase 73 builds around that behavior rather than creating a second idempotency mechanism.

## Artifact identity

`ArtifactIdentity` contains:

- `artifact_id` — deterministic SHA-256 identifier;
- normalized logical filename;
- SHA-256 content checksum;
- identity version.

The identity material is:

`identity_version + filename + checksum`

This means the same logical file content produces the same artifact identity across worker/task executions, while changed content or a changed logical filename produces a different identity.

The physical directory is deliberately excluded from the identity so queue/worker path differences do not create duplicate logical artifacts.

## Task identity and correlation

Celery already provides the execution-level task ID. Phase 73 additionally gives the worker deterministic artifact IDs and operation idempotency keys for logs and correlation.

A task may also carry an optional `run_id` when an upstream application execution has one.

The correlation model is therefore:

`run_id → task_id → artifact_id → idempotency_key → indexer outcome`

The existing public task name `tasks.index_files` is preserved.

## Task payload compatibility

The worker accepts canonical file paths and continues to normalize the legacy task-dictionary shape (`{"path": ...}`) used by the maintained orchestration code. The indexer itself receives a plain list of paths.

This closes an existing contract mismatch without changing the maintained indexer API.

## Failure classification

`classify_failure()` provides a deterministic first boundary:

- terminal: invalid value/type, missing file, or permission failure;
- retryable: other failures, representing infrastructure/transient failures until a more specific provider taxonomy exists.

This classifier is a policy contract, not permission to automatically retry.

## Idempotency stores

Provider-neutral `ArtifactIdempotencyStore` and `BackgroundTaskStore` contracts are introduced with deterministic in-memory implementations for tests/local development.

They intentionally do not claim distributed durability. A future production implementation can map these contracts to Cosmos DB, MongoDB, Redis, or another approved store without changing the application contract.

## Why retries remain disabled

Celery automatic retries are **not enabled** in Phase 73.

The safe sequence is:

1. identify the artifact deterministically;
2. make the artifact operation idempotent;
3. persist operation/task state in a durable provider boundary;
4. prove duplicate and concurrent execution semantics;
5. only then enable automatic retry/late-ack policy.

The current maintained indexer demonstrates sequential unchanged-file protection through persisted hash/version metadata. It does not yet constitute a distributed claim/lease protocol for concurrent workers, so this phase does not pretend otherwise.

## Deterministic validation

Tests cover:

- stable artifact identity for the same content/name;
- identity changes for changed content or logical filename;
- filename normalization;
- operation-scoped idempotency keys;
- missing checksum rejection;
- retryable vs terminal failure classification;
- task ↔ artifact/run correlation contracts;
- prior-result storage;
- legacy task dictionary normalization;
- artifact identity validation at the Celery boundary;
- preservation of no automatic retry and no late acknowledgement policy.

No cloud service, broker, worker, LLM, or live vector/search service is required for these contract tests.

## Deliberate non-goals

Phase 73 does not:

- replace the existing `UserUploadedFileIndexer`;
- introduce a second queue system;
- enable automatic Celery retries;
- claim distributed concurrency safety for local index metadata;
- introduce a new database provider;
- make conversation history part of ingestion processing;
- complete frontend/API upload status UX (Phase 74).

## Exit criterion

Phase 73 is complete when background indexing has a stable artifact identity, task/artifact correlation, deterministic failure classification, compatibility-safe task payload handling, and explicit idempotency boundaries, with retries still gated until durable concurrent idempotency is demonstrated.

The next integration gate is Phase 74 — Frontend / API Integration.
