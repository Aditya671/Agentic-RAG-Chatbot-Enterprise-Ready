# Runtime correctness — Phase 9

## Compatibility-class integration

Phase 9 wires the runtime contracts into a production-facing subclass,
`IntegratedAsyncAgenticAiSystem`, while leaving the existing
`AsyncAgenticAiSystem` compatibility implementation intact.

### Retrieval policy

The integrated class creates an `AgentRuntimeBoundary` backed by a validated
`RetrievalConfig`. The existing `similarity_top_k` setting remains the source
of the runtime value, while the boundary provides a stable application-level
representation of the retrieval policy.

Changing top-k refreshes the boundary after the existing agent reconfiguration,
so the contract stays aligned with the compatibility runtime.

### Response contract

`get_response_contract()` converts the provider response plus retriever
metadata into `AgentResponse`. The historical `get_response()` dictionary
shape remains unchanged for callers that depend on it.

The synchronous bridge likewise preserves its historical return type while
normalizing through the runtime boundary.

### Streaming

`collect_response_stream()` delegates stream collection to the provider-neutral
boundary. Both synchronous and asynchronous response generators therefore use
one application-level collection path.

## Migration strategy

This is intentionally incremental. Existing callers do not need to migrate to
a new response type immediately, and the large compatibility implementation is
not duplicated or rewritten. New code can opt into the integrated class while
future phases progressively move provider-specific seams behind the same
contracts.

## Validation

Tests construct the integration seam without Azure credentials or LLM calls.
They cover response normalization with retriever metadata, asynchronous stream
collection, and retrieval-policy refresh after configuration changes.
