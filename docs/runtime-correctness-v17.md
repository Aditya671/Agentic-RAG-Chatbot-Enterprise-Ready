# Runtime Correctness — Phase 17

## Structured CSV runtime boundary

Phase 17 extracts the optional structured-CSV runtime construction from the converged orchestration class.

The maintained path now follows:

`IntegratedAsyncAgenticAiSystem → structured_csv_runtime → StructuredQueryEngine → PandasQueryEngine`

### What changed

- `structured_csv_runtime.py` owns CSV prompt construction and provider invocation.
- `IntegratedAsyncAgenticAiSystem` delegates `_build_structured_csv_engine()` to that boundary.
- The CSV loader remains on the compatibility runtime because it owns the existing parsing behavior and metadata contract.
- The provider-facing structured query implementation remains isolated behind `StructuredQueryEngine`.
- Dependency-light tests cover the delegation contract and invalid empty input.

### Why this boundary matters

The large compatibility runtime is still an inheritance source, but the maintained runtime no longer needs to know how LlamaIndex's experimental pandas query engine is assembled. This makes the structured-query provider replaceable without changing orchestration state management or the canonical application import surface.

The legacy `agentic_ai_system_upgraded.py` remains intentionally intact in this phase. It continues to provide compatibility behavior while responsibilities are extracted incrementally from the maintained path.

## Validation

No local test suite was executed in this environment. CI remains the authoritative validation path.
