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

## Request and response contracts

`ApplicationRequest` carries question text, optional explicit capability, opaque operation payload, session correlation, and actor correlation.

`ApplicationResult` carries response text, selected capability, non-sensitive metadata, source-backed `Evidence` records, and the run identifier.

The runtime does not persist raw model prompts, tool arguments, tool results, or response bodies in telemetry merely because they pass through the application boundary.

## Evidence boundary

Handlers may return `Evidence` objects with the response. The runtime records each item through the existing observability layer, which creates the corresponding provenance record.

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

A missing capability handler, empty response, malformed handler result, or handler exception is an explicit runtime failure. The runtime records an execution error event and re-raises the original exception to the caller.

## Relationship to the maintained agent runtime

The existing `IntegratedAsyncAgenticAiSystem` remains the maintained provider-aware agent implementation. Phase 68 does not duplicate or replace it. The new boundary is deliberately provider-neutral so the maintained implementation can be integrated without changing its existing retrieval, evidence, provenance, or observability semantics.

## Deterministic validation

The Phase 68 tests cover normalization, default question routing, explicit upload routing, evidence/provenance handoff, response/run correlation, invalid implicit intent, invalid capability types, and handler failure recording.

The tests use injected deterministic handlers and do not require Azure credentials, network access, or an LLM.

## Safety boundaries

Phase 68 does not introduce arbitrary code execution, automatic provider selection, automatic remediation, hidden routing scores, raw telemetry payload capture, or a second competing agent construction path. The retired code-interpreter boundary remains retired.

## Exit criterion

The application has a single, testable boundary through which a request is normalized, assigned an explicit capability, executed by a bounded implementation, connected to evidence/provenance, and returned with an inspectable execution trace.

The next integration gate is to wire the maintained question/retrieval implementation through this boundary without bypassing its existing provider and reliability instrumentation.

## Next phase

Phase 69 completes the document-ingestion-to-RAG journey:

`upload → validation → staging → extraction → chunking → metadata → indexing → retrieval → grounded answer`
