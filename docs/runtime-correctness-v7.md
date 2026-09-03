# Runtime correctness — Phase 7

## Agent execution response boundary

This phase adds a dependency-light application boundary for agent responses.
`AgentResponse` exposes `response_text` and `response_metadata`, while
`extract_text()` normalizes the common response shapes returned by the agent
workflow. `collect_stream()` accepts both synchronous and asynchronous
iterables.

The goal is to keep provider SDK response details out of callers and make the
execution contract independently testable. Existing Azure and LlamaIndex
runtime behaviour is intentionally not changed by this phase.

## Validation

The tests exercise `None`, strings, nested responses, text attributes, blocks,
and both sync and async streams. They do not require Azure credentials, a live
search index, or an LLM call.

## Scope boundary

The existing `AsyncAgenticAiSystem` remains the compatibility runtime. Wiring
this contract into its public response methods is a separate integration step;
this phase establishes and validates the boundary first rather than changing
runtime behaviour without an integration test seam.
