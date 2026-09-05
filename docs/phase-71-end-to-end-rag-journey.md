# Phase 71 — Deterministic Upload → Index → Retrieve → Grounded Answer Journey

## Purpose

Phase 71 proves the complete application RAG journey as one deterministic scenario rather than as separate ingestion and retrieval contract tests.

```text
ApplicationRequest
    ↓
UPLOAD capability
    ↓
DocumentIngestionService
    ↓
maintained indexer
    ↓
indexed artifact identity
    ↓
QUESTION capability
    ↓
RetrievalService
    ↓
maintained agent retrieval path
    ↓
answer + actual source metadata
    ↓
Evidence
    ↓
ApplicationRuntime observability / provenance
    ↓
Harness / Scenario Evaluation
```

The scenario deliberately uses a fake maintained indexer and fake maintained agent surface. It proves application-boundary behavior without requiring Azure, a vector service, an LLM, or network access.

## Scenario fixture

`approval-policy.pdf` is the deterministic uploaded artifact. Its fixture content states that capital approvals require documented approval.

The later question is:

> What does the approval policy require?

The fake maintained retrieval path returns an answer plus source metadata identifying `approval-policy.pdf`, page `1`, with relevance `0.97`.

The raw document content is deliberately present only in the fake retrieval result. The `RetrievalService` converts returned metadata into `Evidence` and excludes `content` from evidence metadata.

## What the scenario proves

### 1. Upload reaches the maintained ingestion implementation

The application uses the existing `DocumentIngestionService` and the maintained indexer surface. The fake indexer records that the exact fixture was submitted and returns an explicit `indexed` result.

### 2. The indexed artifact becomes available to the question path

The fake maintained system refuses to answer as grounded unless the fixture has first been indexed. This binds the question step to the earlier upload step rather than testing retrieval against an unrelated preloaded fixture.

### 3. Retrieval returns source-backed evidence

The question response contains source metadata for the uploaded artifact. `RetrievalService` converts that metadata into `Evidence` with a stable source ID, locator, and relevance value.

### 4. Grounding is explicit

The harness scenario requires the expected evidence source ID and a minimum relevance of `0.9`. The resulting run must report:

- `passed == True`;
- grounding coverage `1.0`;
- retrieval relevance `0.97`.

This remains deterministic relationship-based evaluation rather than semantic or LLM judging.

### 5. Provenance remains attached to the application execution

The canonical runtime records the evidence and creates a provenance record. The scenario asserts that the evidence survives the application boundary and that normal lifecycle events remain present in the trace.

## Why this is a benchmark case

The scenario is intentionally represented using the existing `HarnessCase`, `ScenarioCatalog`, `HarnessEngine`, and scenario evaluation contracts rather than a bespoke integration-test framework.

That makes the case reusable for later architecture comparison:

```text
same fixture
same upload
same question
same evidence expectations
same evaluation rules
          ↓
architecture A / B / C
          ↓
comparable execution records
```

A future architecture variant can therefore execute the same scenario without redefining what success means.

## Determinism boundary

The test does not claim that a real Azure-backed index and model will always produce the exact fixture answer. Its claim is narrower and testable:

> Given the same deterministic maintained-system behavior, the canonical application journey preserves the relationship from uploaded artifact → indexed state → retrieved source → grounded answer → observable evidence.

Live cloud integration remains a separate validation concern.

## Deliberate non-goals

- No second indexer.
- No second retrieval engine.
- No live Azure dependency.
- No live LLM dependency.
- No semantic answer judge.
- No fabricated evidence.
- No new retry policy or background worker.
- No provider-specific benchmark implementation.

## Exit criterion

A named scenario can deterministically exercise upload, indexing, retrieval, grounded answer generation, evidence handoff, and application observability through the existing harness. The same scenario can be replayed as a future regression or architecture benchmark case.
