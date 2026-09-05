# Phase 68 — Canonical Application Runtime

## Purpose

Phase 68 begins the real application journey by establishing one provider-neutral runtime boundary for the user-facing execution path:

```text
ApplicationRequest
    ↓
Normalization
    ↓
Capability Decision
    ↓
Bounded Capability Handler
    ↓
Evidence / Provenance
    ↓
Response Contract
    ↓
ExecutionTrace
```

The phase deliberately does **not** replace the maintained Azure implementation or introduce another cloud provider. It creates the application-layer seam that the existing provider-aware agent runtime can plug into without becoming the public contract itself.

## Canonical boundary

`ApplicationRuntime` owns five responsibilities:

1. normalize the incoming request;
2. select a capability deterministically;
3. dispatch to an explicitly configured handler;
4. validate and record returned evidence through `AgentObservability`;
5. return a stable response together with the execution trace.

Provider-specific services remain behind injected handlers. This keeps Azure, LlamaIndex, search, graph retrieval, and structured-data implementations out of the application contract.

## Capability selection

The initial capability set is intentionally small:

- `question` — default for a non-empty question;
- `upload` — selected only when the API/client explicitly declares upload intent;
- `index_status` — selected only when explicitly requested.

Natural-language routing is not used to infer upload or status operations. This prevents an LLM from silently deciding which application operation should execute.

Future capabilities can be added only when their contract, implementation, deterministic tests, and integration path are defined.

## Request and response contracts

`ApplicationRequest` carries:

- question text;
- optional explicit capability;
- opaque operation payload;
- session correlation;
- actor correlation.

`ApplicationResult` carries:

- response text;
- selected capability;
- non-sensitive metadata;
- source-backed `Evidence` records;
- run identifier.

The runtime does not persist raw model prompts, tool arguments, tool results, or response bodies in telemetry merely because they pass through the application boundary.

## Evidence boundary

Handlers may return `Evidence` objects with the response. The runtime records each item through the existing observability layer, which creates the corresponding provenance record.

This maintains the established separation:

```text
provider result
      ↓
Evidence
      ↓
ProvenanceRecord
      ↓
ExecutionTrace
```

Evidence remains source-backed material. A response, recommendation, retrospective finding, or capability decision does not become evidence merely because it was emitted by the runtime.

## Failure behavior

A missing capability handler, empty response, malformed handler result, or handler exception is an explicit runtime failure.

The runtime records an execution error event and preserves the failure outcome in the trace before re-raising the original exception to the caller. It does not silently convert provider failures into successful natural-language responses.

## Relationship to the maintained agent runtime

The existing `IntegratedAsyncAgenticAiSystem` remains the maintained provider-aware agent implementation. It already converges retrieval, optional graph retrieval, optional structured CSV analysis, response contracts, and observability behind explicit seams.

Phase 68 therefore adds an application-facing boundary rather than creating a second agent implementation. Integration of the maintained agent into this boundary should occur only after the request/capability contracts are stable and covered by deterministic tests.

## Deterministic validation

The Phase 68 tests cover:

- whitespace normalization;
- default question routing;
- explicit upload routing without a question;
- evidence capture and provenance through observability;
- response/run correlation;
- explicit rejection of missing implicit intent;
- handler failure recording and re-raising.

The tests use injected deterministic handlers and do not require Azure credentials, network access, or an LLM.

## Safety boundaries

Phase 68 does not introduce:

- arbitrary code execution;
- automatic provider selection;
- automatic remediation;
- hidden routing scores;
- raw telemetry payload capture;
- a second competing agent construction path.

The retired code-interpreter boundary remains retired.

## Exit criterion

The application has a single, testable boundary through which a request is normalized, assigned an explicit capability, executed by a bounded implementation, connected to evidence/provenance, and returned with an inspectable execution trace.

The next integration step is to wire the maintained agent implementation into the `question` capability without bypassing its existing provider and reliability boundaries.

## Next phase

Phase 69 completes the document-ingestion-to-RAG journey:

`upload → validation → staging → extraction → chunking → metadata → indexing → retrieval → grounded answer`
