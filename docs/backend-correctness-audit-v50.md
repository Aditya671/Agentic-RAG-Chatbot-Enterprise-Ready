# Backend Correctness Audit — Phase 50

## Objective

Audit the maintained `backend/` implementation for behavioral defects, not merely syntax/style problems. The audit uses current callers/contracts, dependency versions, and provider API contracts as the reference. Historical `*_upgraded.py` files are treated as evidence only; they are not restored when a later architecture intentionally removed their capability.

## Phase 50 findings and fixes

| Area | Defect | Resolution |
|---|---|---|
| `process_doc/orchestrator/pipeline.py` | Checksums were reserved before processing completed, making failures permanently look processed | Reserve while running; commit only after success; release on failure/HITL |
| `process_doc/orchestrator/hitl_queue.py` | DB failures were swallowed; resolved items could be resolved again; pending order was nondeterministic | Raise explicit persistence errors, require `PENDING`, order by creation time, add busy timeout/index |
| `process_doc/extractors/azure_extractor.py` | Pipeline instantiated an unconfigured extractor and extraction confidence was not exposed | Environment-backed initialization, explicit configuration failure, OCR confidence aggregation, close lifecycle |
| `process_doc/extractors/multimodal_extractor.py` | PDF handles were not explicitly closed and multimodal response content could be non-string | Context-managed PDF lifecycle and normalized response conversion |
| `process_doc/processors/classifier.py` | Classification exposed inconsistent confidence semantics | Stable `confidence` and `confidence_score` contract with validation |
| `process_doc/processors/pii_redactor.py` | Optional Presidio absence could silently produce unsafe behavior | Conservative local redaction fallback; strict mode remains available; redaction failures never masquerade as redacted text |
| `process_doc/processors/local_nlp_processor.py` | Empty labels and nondeterministic set output; error shape violated declared return contract | Input validation, deterministic sorted entities, stable fallback/error behavior |
| `process_doc/processors/cv_preprocessor.py` | Image decoding/write failures were not validated and output-path behavior was ambiguous | Validate decoded images and `imwrite`, return actual generated path |
| `process_doc/orchestrator/hierarchical_indexer.py` | Numeric relationship keys relied on undocumented enum ordering and metadata could overwrite structural fields | Typed `NodeRelationship.PARENT/CHILD`, validation, protected structural metadata |
| `tasks.py` | Invalid Celery time-limit environment values were accepted at import | Positive-integer validation and soft-limit < hard-limit invariant |

## Remaining audit

The backend contains additional provider connectors and orchestration/indexing modules. They are being audited in subsequent passes by subsystem rather than being mass-rewritten in one change. Each pass must produce either a verified fix, a regression test, or an explicit finding that is intentionally deferred because it requires provider/infrastructure integration testing.

## Validation rule

CI is authoritative for dependency installation, compilation, Ruff, tests, and wheel building. Cloud integrations are not considered production-verified by unit tests alone.
