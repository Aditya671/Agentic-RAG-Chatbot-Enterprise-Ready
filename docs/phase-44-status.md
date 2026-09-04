# Phase 44 — Celery indexing task canonicalization

Status: ready for review.

The Celery uploaded-file indexing task now has one maintained implementation at `backend/tasks.py`. The historical `tasks_upgraded.py` module is compatibility-only, while migration-era tests and the upgrade report have been removed from `src/`.

## Preserved contract

- Public Celery task name remains `tasks.index_files`.
- Redis remains the default broker and result backend.
- The worker constructs `UserUploadedFileIndexer` locally.
- `memory=None` remains explicit because memory/service objects must not cross the Celery message boundary.
- The result returned by `index_uploaded_files` is returned unchanged.

## Hardened boundary

- `.env` loading no longer overrides runtime environment configuration.
- JSON task/result serialization is explicit and pickle is not accepted.
- Task arguments are validated before worker-local indexer construction.
- Started-state tracking and configurable soft/hard time limits remain enabled.
- Automatic retries and late acknowledgements are intentionally not enabled until the indexer's idempotency contract is established.

## Next dependency question

The next indexing-layer work should establish whether `UserUploadedFileIndexer.index_uploaded_files` is idempotent and safe for retry/redelivery semantics. Phase 44 does not invent that guarantee.
