# Phase 69 — Canonical Document Ingestion Journey

## Purpose

Phase 69 connects the canonical application upload capability to the maintained uploaded-file indexer without creating a second ingestion pipeline.

The resulting boundary is:

```text
ApplicationRequest
    ↓
explicit upload capability
    ↓
DocumentIngestionService
    ↓
maintained UserUploadedFileIndexer
    ↓
validation / safe staging
    ↓
extraction / chunking / metadata
    ↓
vector + summary indexing
    ↓
retrieval through the maintained agent
    ↓
source-backed Evidence / Provenance
```

The existing indexer remains the implementation owner for document processing. The new service owns the application-facing contract and normalization of its result.

## Why this is an integration phase

The repository already contains a hardened `UserUploadedFileIndexer`. It validates supported extensions and file size, keeps uploads under a controlled directory, computes SHA-256-based identity, persists metadata atomically, supports unchanged-file skipping, chunks documents, and persists vector/summary indexes. Reimplementing those behaviors in a new application service would create competing semantics.

Phase 69 therefore deliberately wraps the maintained implementation instead of duplicating it.

## Canonical ingestion contract

`DocumentIngestionService.ingest()` accepts a non-empty upload sequence and delegates to the maintained indexer's `index_uploaded_files(file_list=...)` API.

The service returns:

- `IngestionArtifact` — filename, status, optional chunk count, reason, and future-safe identity fields;
- `IngestionResult` — immutable batch result with accepted and failed views;
- preserved raw indexer metadata for application-level inspection.

Recognized outcomes are:

- `indexed` — the artifact was processed for indexing;
- `skipped` — the maintained indexer determined the artifact was unchanged;
- `failed` — the indexer explicitly reported an artifact failure.

A malformed indexer response is a contract error rather than a successful ingestion.

## Duplicate semantics

Duplicate/unchanged semantics are not reimplemented by Phase 69. The maintained indexer remains authoritative. Its existing metadata uses file identity and checksum information and can return an unchanged file as `skipped` rather than rebuilding the index.

This means the application layer can distinguish:

```text
new/changed artifact → indexed
unchanged artifact    → skipped
failed artifact       → failed
```

The service does not silently convert a skipped artifact into an indexing success or claim that a failed artifact succeeded.

## Application-runtime integration

The upload handler in `application_runtime_adapter.py` now obtains the maintained `local_file_indexer` from the agent system and invokes `DocumentIngestionService`.

The application therefore no longer treats the legacy agent upload response as the canonical upload contract.

The response is deterministic and bounded:

```text
Document ingestion completed: N indexed, M unchanged.
```

If the maintained indexer reports failed artifacts, the application path raises an explicit runtime error. It does not emit a false success response.

## Validation ownership

Validation remains layered:

1. Application boundary rejects an empty upload batch.
2. The maintained indexer validates individual uploaded artifacts.
3. The maintained indexer enforces filename/path safety and supported file types.
4. The maintained indexer enforces configured maximum size.
5. Index construction rejects empty document sets and invalid chunk configuration.
6. Index persistence and metadata updates remain owned by the existing indexer.

This prevents application-level validation from drifting away from the actual ingestion implementation.

## Retrieval and evidence boundary

Phase 69 does not fabricate retrieval evidence from ingestion metadata. Evidence is still created from actual retrieval metadata by the Phase 68 application adapter and recorded through `AgentObservability`.

Therefore:

```text
ingestion result ≠ evidence
index metadata   ≠ evidence
summary          ≠ evidence
retrieved source → Evidence → ProvenanceRecord
```

This distinction is important for grounded-answer evaluation and later architecture benchmarking.

## Error semantics

Errors remain visible at the layer that owns them:

- invalid application upload batch → `ValueError`;
- malformed indexer contract → `TypeError`;
- indexer exception → propagated to the application runtime and recorded by its execution lifecycle;
- explicit failed artifact result → application-level `RuntimeError` rather than false success.

No retry policy is introduced by this phase. In particular, Phase 69 does not enable Celery retries or claim artifact-level idempotency beyond the maintained indexer's existing unchanged-file behavior.

## Deterministic validation

The Phase 69 tests use a fake indexer implementing the same public async method as the maintained implementation. They verify:

- upload batch validation;
- delegation to `index_uploaded_files`;
- indexed and skipped normalization;
- explicit failed-artifact handling;
- malformed result rejection;
- canonical application upload integration;
- failure propagation through the application runtime.

No Azure credentials, external network, LLM, vector service, or Celery worker is required for these contract tests.

## Safety boundaries

Phase 69 does not introduce:

- a second document indexer;
- arbitrary code execution;
- hidden upload routing;
- automatic provider selection;
- automatic retries;
- raw document content in observability telemetry;
- an LLM judge for ingestion success;
- fabricated evidence or provenance.

## Exit criterion

The canonical application upload capability now has a stable ingestion contract around the maintained indexing implementation. New/unchanged/failed outcomes are distinguishable, failures remain visible, and the ingestion path can feed the existing retrieval/evidence pipeline without bypassing the reliability boundary.

## Next integration gate

The next phase should close the remaining end-to-end retrieval boundary: prove that a successfully indexed artifact can be retrieved through the maintained question path and that the resulting answer carries source-backed evidence suitable for the existing evaluation and benchmark infrastructure.
