# Phase 45 — User-upload indexer canonicalization

Status: ready for review.

The user-upload indexing implementation is now owned by the historical public module path `backend.indexer.user_uploaded_file_indexer`. The former `*_upgraded.py` implementation is removed rather than retained as a second runtime surface.

## Preserved behavior

- `UserUploadedFileIndexer` remains importable through the established public module paths.
- Uploaded-file validation, path safety, hashing, metadata persistence, vector/summary indexing, querying, and optional Azure Blob backup are preserved.
- The top-level `backend.user_uploaded_file_indexer` compatibility import remains unchanged.
- Celery continues to construct the indexer inside the worker.

## Idempotency boundary

The implementation has hash/version-aware reindex decisions: unchanged files are skipped while missing, changed, stale, or version-mismatched metadata causes reindexing.

This phase deliberately does **not** claim full artifact-level idempotency for retry/redelivery. The current indexing path constructs and persists indexes from the files selected for the current operation; proving safe incremental merge semantics across previously persisted vector and summary indexes requires separate LlamaIndex lifecycle validation.

Accordingly, Phase 44's no-automatic-retry and no-late-ack policy remains correct until that artifact-level guarantee is established.

## Migration cleanup

- Removed `user_uploaded_file_indexer_upgraded.py`.
- Removed the migration-era indexer test and upgrade report from `src/`.
- Added maintained source-boundary coverage under `tests/`.

## Next dependency

Before enabling Celery retry/redelivery semantics, validate incremental index merge, duplicate prevention, partial-failure recovery, and concurrent worker behavior against the persisted vector and summary indexes.
