# Phase 48 — Remaining Enhanced Runtime Reconciliation

## Scope

This phase continues the repository-wide reconciliation of historical `*_upgraded.py` implementations. The suffix is not treated as evidence of duplication; enhanced behavior is compared with the maintained runtime before promotion.

## Promoted implementations

The following historical enhanced implementations are now the canonical runtime surfaces:

- Azure Blob file retrieval
- S3 file retrieval
- LlamaIndex document ingestion
- LLM reranking

The historical upgraded copies are removed for these components.

## Azure Blob retrieval

The canonical adapter now includes dependency-injected clients, connection-string and passwordless authentication paths, extension normalization, deterministic latest-file selection, validation of concurrency and filenames, metadata extraction, stream-position preservation, and structured logging.

## S3 retrieval

The canonical adapter now includes dependency-injected clients, standard boto3 credential-chain support, optional profile/session configuration, lazy paginated object discovery, deterministic latest-object selection, response-body cleanup, validation, metadata preservation, and structured logging.

## LlamaIndex ingestion

The canonical ingestion runtime now owns the production implementation directly rather than importing a second runtime module. It preserves current LlamaIndex APIs, checksum/version-aware indexing, deterministic document and chunk IDs, explicit PDF resource cleanup, DataFrame ingestion, semantic search, and the historical `upsert_documents_to_index` contract.

## Reranking

The canonical reranker now validates all numeric configuration, supports callback and prompt injection, preserves the existing LlamaIndex `LLMRerank` implementation, and normalizes initialization failures without hiding the underlying exception.

## Test boundary

Retriever regression tests now import the canonical modules rather than historical upgraded modules. Tests cover dependency injection, validation, latest-file selection, deterministic tie-breaking, stream behavior, metadata, body cleanup, and local persistence.

## Remaining compatibility files

Other `*_upgraded.py` files that have already been reduced to compatibility-only import surfaces are not duplicated again. They remain only where a historical import path still has compatibility value. Retired code-execution and other superseded capabilities are not restored.

## Verification

GitHub Actions remains authoritative for dependency installation, source compilation, Ruff, tests, and wheel creation. No cloud end-to-end behavior is claimed solely from unit tests.
