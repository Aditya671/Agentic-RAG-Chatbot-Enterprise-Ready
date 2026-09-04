# Runtime correctness — Phase 14

## Canonical tool-construction boundary

Phase 12 made the converged runtime the canonical agent surface. Phase 14 removes
one remaining architectural coupling from that path: `agent_builder.py` no
longer accesses name-mangled methods on the legacy `AsyncAgenticAiSystem`.

`tool_factory.py` owns construction of the current LlamaIndex `FunctionTool`
and `RetrieverTool` objects. Application orchestration supplies validated
callables and retrieval objects; provider-specific construction remains at the
edge.

### Why this matters

- The canonical agent builder no longer depends on private parent implementation
  details.
- Tool construction is independently testable without Azure credentials.
- The historical upgraded runtime can continue to exist as a compatibility
  implementation while its private tool helpers stop being part of the new
  runtime's dependency graph.
- The public orchestration package explicitly exposes the maintained tool
  factory alongside the existing runtime contracts.

## Compatibility

No public application tool names or callable behavior were intentionally
changed. The change replaces only the mechanism used to construct the tools.
The legacy private helpers remain available to older callers until the
superseded runtime is retired in a later cleanup phase.

## Validation

`tests/test_tool_factory.py` verifies callable validation, retriever validation,
and provider delegation using lightweight LlamaIndex stubs. No Azure resources,
model credentials, or external services are required.
