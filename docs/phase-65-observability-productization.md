# Phase 65 — Agent Observability Productization

## Purpose

Phase 65 turns the existing runtime instrumentation into a small operational capability: an engineer should be able to locate a run, inspect its lifecycle, follow retrieval/evidence provenance, and identify failing phases without reconstructing raw application logs.

The implementation remains provider-neutral. It does not require a hosted telemetry vendor, tracing SDK, dashboard, or external collector.

## Operational trace model

The intended lifecycle is:

`request → session/actor → agent decision → tool call → retrieval → evidence → model call → response/outcome`

`ExecutionTrace` now carries stable `request_id`, `session_id`, and optional `actor_id` correlation fields in addition to its existing `run_id`. These identifiers are correlation metadata; they are not a license to store prompts, model responses, documents, credentials, or other sensitive payloads.

The instrumentation facade provides explicit records for:

- agent lifecycle events;
- decision/strategy events;
- tool calls;
- model calls with provider/model and optional token counts;
- retrieval/evidence records with provenance links;
- duration and error status.

## Operational query surface

`ObservabilityService` is the product-facing read layer over a trace store.

### Run inspection

`get_run(run_id)` returns a `TraceInspection` containing:

- the complete structured trace;
- total run duration when timestamps are valid;
- tool, retrieval, and model call counts;
- successful and failed event counts;
- phases containing explicit error events;
- provenance identifiers attached to recorded evidence.

This creates a deterministic inspection path from a run identifier to the execution facts that explain its behavior.

### Trace search

`TraceQuery` supports bounded filtering by:

- request id;
- session id;
- actor id;
- outcome;
- lifecycle phase;
- event status;
- result limit.

The service deliberately searches the store's bounded recent window rather than introducing an unbounded query engine in this phase.

### Health summary

`ObservabilityService.health()` delegates aggregate health calculation to the existing monitoring primitive. This keeps the existing operational metrics as the source of truth while making them accessible beside trace inspection.

## Safe telemetry boundary

The observability layer records execution facts, not application payloads. Callers should prefer:

- identifiers over raw request text;
- hashes over raw tool arguments;
- result metadata over raw tool output;
- provider/model names over prompts;
- token counts over prompt/completion content;
- evidence source identifiers, locators, hashes, and relevance over unnecessary document content.

`record_tool_call()` intentionally exposes `arguments_hash` and an optional short `result_summary`, rather than accepting raw arguments/results. `record_model_call()` records provider/model and token metadata only.

Applications remain responsible for ensuring that custom `attributes` and opaque correlation identifiers do not contain secrets or personal data. The reliability layer does not attempt to discover or redact arbitrary application payloads.

## Why this is not a vendor integration

A vendor-specific exporter or dashboard would prematurely couple the reliability model to an external telemetry system. Phase 65 establishes the internal contract first:

1. capture structured facts;
2. persist them through the existing store abstraction;
3. query and inspect them deterministically;
4. compute operational summaries from those same facts;
5. add external exporters only after the contract proves stable.

This preserves the repository's provider-neutral architecture and makes a future OpenTelemetry or hosted observability adapter an integration concern rather than the definition of observability itself.

## Validation

Deterministic tests cover:

- correlation identifiers and lifecycle metadata;
- tool/model/evidence instrumentation;
- provenance visibility;
- run inspection;
- request/session filtering;
- health summaries;
- query limit validation.

No claim of external dashboard, CI, or production telemetry validation is made by this phase.

## Exit criterion

An engineer can take a run identifier and determine what happened across decision, tool, retrieval, evidence, model, and outcome stages from structured records, without reconstructing the execution from raw logs.

## Next phase

Phase 66 can build the Agent Retrospective Engine on top of these operational facts, turning individual traces into structured post-run findings and recommendations while keeping the distinction between observed facts and derived analysis explicit.
