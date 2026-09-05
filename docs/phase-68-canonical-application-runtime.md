# Phase 68 — Canonical Application Runtime

## Purpose

Phase 68 establishes the application-facing boundary that sits above the maintained provider-aware agent runtime.

The goal is not another agent implementation. The goal is one stable application journey:

```text
ApplicationRequest
    ↓
Normalize
    ↓
Capability Decision
    ↓
Capability Handler
    ↓
Evidence / Provenance
    ↓
ApplicationResult
    ↓
ExecutionTrace
```

The existing `IntegratedAsyncAgenticAiSystem` remains responsible for provider-aware agent execution. `ApplicationRuntime` owns application semantics and the stable boundary consumed by an API or frontend.

## Application contract

`ApplicationRequest` contains:

- optional natural-language `question`;
- explicit `capability` when the client already knows the operation;
- structured `payload` for non-question operations;
- optional `session_id`;
- optional `actor_id`.

Supported capabilities in this phase are:

- `question`;
- `upload`;
- `index_status`.

Capability selection is deterministic. A question defaults to `question`; upload and status operations require explicit capability intent. The runtime does not ask an LLM to decide which application operation should run.

## Canonical response

`ApplicationResult` exposes:

- response text;
- selected capability;
- application metadata;
- structured `Evidence` objects;
- the runtime `run_id`.

`ApplicationExecution` additionally returns the complete `ExecutionTrace` for callers that need inspection, replay, or downstream evaluation.

## Maintained runtime integration

`build_application_runtime()` adapts the maintained `AsyncAgenticAiSystem` without moving provider logic into the application layer:

- question → existing `get_response()` path;
- upload → existing `upload_and_index_files()` path;
- index status → existing `check_indexing_status()` path.

Retrieval metadata is translated into the existing evidence contract. Raw retrieved content is deliberately excluded from the application evidence metadata.

This gives the real runtime a stable application seam while preserving the established provider boundaries, retrieval configuration, and reliability instrumentation.

## Observability

Every application execution records:

1. request normalization;
2. capability selection;
3. capability execution;
4. evidence capture when evidence is returned;
5. response emission;
6. explicit execution errors.

The application trace retains session and actor correlation identifiers when supplied.

The provider-aware runtime may also emit its own internal trace. These are intentionally separate concerns: the application trace describes the user-facing journey, while the provider runtime trace describes the internal agent execution.

## Error behavior

The application boundary rejects:

- non-`ApplicationRequest` input;
- empty questions when capability is not explicit;
- unconfigured capabilities;
- empty handler responses;
- malformed handler result types;
- non-`Evidence` objects in the evidence collection.

Handler exceptions are recorded as an explicit error event and re-raised. The runtime does not convert failures into successful-looking responses.

## Evidence boundary

Evidence is accepted only as structured `Evidence` objects. The adapter strips raw retrieval body fields such as `content`, `excerpt`, and `text` from evidence metadata.

The runtime therefore preserves the existing distinction between:

- source-backed evidence;
- execution telemetry;
- application response data.

No finding, recommendation, or retrospective artifact is treated as evidence.

## Deterministic tests

Focused tests cover:

- whitespace normalization;
- deterministic default capability selection;
- explicit upload/status routing;
- stable application response shaping;
- trace correlation;
- evidence recording;
- maintained-runtime adaptation;
- raw retrieval-body exclusion;
- handler failure recording and re-raising.

Tests use fake handlers/runtime systems and do not require Azure, LlamaIndex, a live search index, or a production queue.

## Intentionally out of scope

Phase 68 does not yet complete the entire user journey. In particular:

- document ingestion semantics remain Phase 69;
- structured CSV/data-analysis completion remains Phase 70;
- persistence/conversation completion remains Phase 71;
- background-processing/idempotency completion remains Phase 72;
- frontend/API integration remains Phase 73.

The retired arbitrary code-execution surface remains retired.

## Exit criterion

The maintained agent implementation can be consumed through one explicit application boundary with deterministic capability selection, a stable response contract, structured evidence handoff, and application-level observability.

## Next phase

Phase 69 completes the document ingestion → indexing → retrieval journey, including artifact identity, duplicate semantics, visible indexing failures, preserved source metadata, deterministic fixtures, and response-linked evidence.
