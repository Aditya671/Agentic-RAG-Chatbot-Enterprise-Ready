# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.23] - 2026-09-04

### Changed

- Promoted `backend.indexer.user_uploaded_file_indexer` to the canonical maintained `UserUploadedFileIndexer` implementation.
- Removed the duplicate `user_uploaded_file_indexer_upgraded.py` runtime implementation.
- Preserved the established public import paths and worker-local Celery construction.
- Preserved hash/version-aware reindex decisions, path safety, metadata persistence, vector/summary indexing, querying, and optional Azure Blob backup.
- Explicitly documented that current per-file skip/reindex behavior is not yet a proof of artifact-level idempotency for retry/redelivery.
- Moved maintained indexer boundary coverage to the top-level `tests/` suite.
- Removed the migration-era indexer test and upgrade report from `src/`.

---

## [0.2.22] - 2026-09-04

### Changed

- Promoted `backend.tasks` to the canonical Celery uploaded-file indexing implementation.
- Reduced `tasks_upgraded.py` to a compatibility-only re-export.
- Preserved the public `tasks.index_files` task name and worker-local indexer construction.
- Preserved JSON serialization, started-state tracking, configurable time limits, validation, and explicit async execution boundary.
- Intentionally retained the no-retry/no-late-ack policy until `index_uploaded_files` idempotency is established.
- Moved maintained Celery regression coverage to the top-level `tests/` suite.
- Removed the migration-era Celery test and upgrade report from `src/`.

---

## [0.2.21] - 2026-09-04

### Changed

- Promoted `backend.credentials.aws_credential_manager` to the canonical AWS credential and Secrets Manager implementation.
- Reduced `aws_credential_manager_upgraded.py` to a compatibility-only re-export.
- Preserved Boto3's default credential provider chain, environment-first secret lookup, and AWS Secrets Manager fallback.
- Preserved configurable retries, timeouts, optional caching, and normalized provider errors from the hardened implementation.
- Moved AWS credential regression coverage to the maintained top-level `tests/` suite.
- Removed the migration-era AWS credential regression suite and upgrade report.

---

## [0.2.20] - 2026-09-04

### Changed

- Consolidated Azure AI Search initialization on the canonical `backend.indexer.index_engine` implementation.
- Reduced `azure_search_initializer.py` to a compatibility adapter for the historical import path.
- Removed the duplicate `azure_search_initializer_upgraded.py` implementation.
- Removed the migration-era Azure Search initializer regression suite and upgrade report.
- Preserved the existing initializer API, including `initialize_index` and `close_index`.

---
