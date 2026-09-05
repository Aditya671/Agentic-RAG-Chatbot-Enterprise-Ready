# Phase 70 — Retrieval-to-Grounded-Answer Boundary

## Purpose

Phase 70 closes the question-side application boundary established in Phase 68 and connected to ingestion in Phase 69. The maintained agent remains responsible for retrieval and answer generation; this phase provides a stable application contract around that result.

```text
ApplicationRequest
    ↓
explicit question capability
    ↓
RetrievalService
    ↓
maintained agent question path
    ↓
retrieval/tool execution
    ↓
answer + retriever metadata
    ↓
source metadata → Evidence
    ↓
ApplicationRuntime observability
    ↓
ProvenanceRecord / evaluation
```

## Contract ownership

`RetrievalService` owns only the boundary contract:

- rejects empty questions;
- requires a structured agent response;
- requires non-empty answer text;
- normalizes returned source metadata into `Evidence`;
- never invents evidence when no sources were returned.

The maintained agent continues to own retrieval strategy, tool execution, reranking, graph-RAG behavior, model selection, and answer generation.

## Evidence boundary

Only metadata returned by the maintained retrieval path becomes evidence. Raw source content is deliberately excluded from `Evidence.metadata` so the application contract does not duplicate document bodies into reliability telemetry.

An answer with no returned sources is represented as `grounded == False`. The service does not manufacture a source merely because the answer sounds plausible.

## End-to-end application behavior

The canonical question capability now uses `RetrievalService` and passes its evidence to `ApplicationRuntime`. The runtime validates each `Evidence` instance and records it through the existing observability/provenance mechanism.

This creates the intended separation:

```text
retrieval implementation → retrieval result
application runtime      → execution lifecycle
observability             → evidence/provenance
evaluation                → grounding assessment
```

## Deterministic validation

Tests use a fake maintained-agent surface and verify:

- question normalization and delegation;
- answer preservation;
- source metadata → `Evidence` conversion;
- source content is not copied into evidence metadata;
- empty answers are rejected;
- absence of sources remains explicitly ungrounded.

No Azure service, vector store, LLM, or network call is required for contract validation.

## Deliberate non-goals

- No second retrieval engine.
- No LLM-as-judge for grounding.
- No fabricated citations.
- No retrieval result caching.
- No provider-specific retrieval API.
- No automatic fallback provider.
- No new reranker or retrieval algorithm.

## Exit criterion

A canonical application question can now receive the maintained agent's generated answer together with source-backed evidence through one application boundary. The evidence is inspectable by the existing observability and evaluation infrastructure.

## Next gate

The next phase should validate the complete upload → index → retrieval journey with deterministic scenario fixtures, including the relationship between an ingested artifact and the source evidence returned by a later question. That scenario can then become a benchmark case rather than merely an integration test.
