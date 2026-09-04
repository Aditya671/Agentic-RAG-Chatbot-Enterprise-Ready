# Runtime Correctness — Phase 17

## Structured CSV runtime boundary

Phase 17 extracts the optional structured-CSV runtime construction from the converged orchestration class.

The maintained path now follows:

`IntegratedAsyncAgenticAiSystem → structured_csv_runtime → StructuredQueryEngine → pandas`

### What changed

- `structured_csv_runtime.py` owns CSV context/prompt construction and engine creation.
- `StructuredQueryEngine` uses an LLM only for intent planning and pandas for deterministic execution.
- Generated Python is never evaluated.
- `IntegratedAsyncAgenticAiSystem` delegates `_build_structured_csv_engine()` to that boundary.
- The CSV loader remains on the runtime because it owns the existing parsing behavior and metadata contract.
- The provider-facing structured query implementation remains isolated behind `StructuredQueryEngine`.
- Dependency-light tests cover construction, invalid input, aggregation, filtering, and async behavior.

### Why this boundary matters

Structured analysis is now a deterministic software capability rather than an arbitrary-code execution surface. This removes the need for a separate experimental query dependency while keeping natural-language dataframe analysis available to the agent.

The legacy `agentic_ai_system_upgraded.py` remains an import-compatible compatibility surface and contains no independent runtime implementation.

## Validation

No local test suite was executed in this environment. CI remains the authoritative validation path.
