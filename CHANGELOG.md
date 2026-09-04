# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.25] - 2026-09-04

### Fixed

- Aligned the direct pandas dependency with `llama-index-experimental==0.6.6`, which requires `pandas<2.3.0`.
- Replaced the incompatible `pandas==3.0.5` constraint with `pandas>=2.2.0,<2.3.0` so the project's declared dependency graph can be resolved by pip.
- Kept the existing `StructuredQueryEngine` adapter and PandasQueryEngine functionality intact; this is a dependency-compatibility correction, not a structured-query redesign.

---

## [0.2.24] - 2026-09-04

### Changed

- Re-audited the historical enhanced `*_upgraded.py` implementations against their current runtime counterparts instead of treating the suffix as evidence of duplication.
- Restored the enhanced Cosmos DB data layer as the maintained implementation, including parameterized queries, partition-safe operations, lifecycle cleanup, and current Chainlit data-layer methods.
- Restored the enhanced MongoDB data layer using PyMongo's native async client, replacing the older Motor-backed implementation.
- Reconciled `UploadedFileWrapper` so both file-backed and explicit in-memory upload payloads remain supported without leaking content through `repr()`.
- Restored the missing `upsert_documents_to_index` compatibility helper required by the PDF ingestion surface.
- Added regression coverage for the reconciled data-layer, upload-wrapper, and ingestion boundaries.
- Explicitly classified obsolete code-execution/PandasAI migration artifacts as out of scope rather than reintroducing retired product capabilities.

---

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

## [0.2.19] - 2026-09-04

### Changed

- Moved the maintained orchestration implementation from the historical `agentic_ai_system_upgraded.py` path into an explicit internal runtime module.
- Kept `agentic_ai_system.py` as the stable public agent surface, including the upload wrapper contract.
- Reduced `agentic_ai_system_upgraded.py` to a compatibility-only re-export.
- Updated the integrated runtime to inherit from the internal canonical runtime owner.
- Added maintained regression coverage for orchestration ownership and compatibility direction.

---

## [0.2.18] - 2026-09-04

### Changed

- Promoted `backend.indexer.index_engine` to the canonical Azure AI Search/LlamaIndex initializer.
- Reduced `index_engine_upgraded.py` to a compatibility import.
- Preserved sync/async clients, current and legacy schema mappings, validation, explicit index-management, and lifecycle behavior.
- Removed the migration-era index-engine regression suite and upgrade report.

---

## [0.2.17] - 2026-09-04

### Changed

- Removed the obsolete `runtime_components.py` implementation, which still carried the retired code-interpreter construction surface.
- Consolidated optional reranker and GraphRAG construction on `component_runtime.py`.
- Removed the obsolete runtime-components regression suite.
- Removed the first-generation orchestration upgrade report; maintained regression coverage now lives under `tests/`.
- Removed the retired code-interpreter builder from the public orchestration package exports.

---

## [0.2.16] - 2026-09-04

### Changed

- Consolidated PDF ingestion onto the canonical multi-format `llama_indexer` pipeline.
- Reduced `pdf_indexer.py` to a compatibility adapter with no independent indexing implementation.
- Removed the duplicate `pdf_indexer_upgraded.py` implementation.
- Removed the migration-era PDF indexer regression suite and upgrade report.
- Preserved the historical PDF helper surface through delegation to canonical ingestion contracts.

---
