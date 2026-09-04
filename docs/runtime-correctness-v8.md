# Runtime correctness — Phase 8

## Agent runtime integration adapter

Phase 8 introduces `AgentRuntimeAdapter` as the integration seam between the
existing compatibility agent and the stable runtime contracts established in
Phase 7.

### What it standardizes

- validates user questions before execution;
- exposes the configured retrieval policy through one application-facing
  property;
- normalizes asynchronous agent execution into `AgentResponse`;
- normalizes synchronous or asynchronous streaming into plain text;
- keeps provider-specific response objects out of callers;
- defines the minimum executor protocol needed by the adapter.

### Why an adapter

`AsyncAgenticAiSystem` is a large compatibility-oriented implementation with
Azure, LlamaIndex, task execution, CSV, graph, and code-interpreter concerns.
Changing all of those concerns at once would make the refactor difficult to
review and easy to regress.

The adapter provides a narrow migration seam: callers can consume stable
runtime behaviour while the existing engine remains intact. The next step can
replace individual internal seams—retriever construction, CSV querying, and
public response handling—incrementally.

## Validation

The tests use a small fake executor. They verify retrieval policy exposure,
async execution normalization, streaming normalization, input validation, and
constructor validation without Azure credentials, network access, a live
search index, or an LLM call.
