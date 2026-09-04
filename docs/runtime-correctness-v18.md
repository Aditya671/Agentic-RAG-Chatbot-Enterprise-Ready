# Runtime Correctness — Phase 18

## Optional runtime component factories

Phase 18 introduces a provider-facing factory boundary for the runtime's optional components: reranking, GraphRAG, and isolated code execution.

The boundary is intentionally small:

`Runtime Orchestration → Runtime Component Factories → Provider Components`

### What changed

- `component_runtime.py` owns construction of the optional reranker, GraphRAG system, and code interpreter.
- Disabled components return `None` without constructing provider clients.
- Reranker depth remains bounded by the active retrieval depth and the existing maximum of five candidates.
- Provider initialization failures retain the existing resilient behavior by returning `None`.
- The maintained converged runtime now delegates optional component construction through the factories.
- Dependency-isolated tests cover disabled components, provider argument forwarding, and failure handling.

### Migration intent

The large `agentic_ai_system_upgraded.py` compatibility implementation still contains historical private builders. They remain because that module is still the inheritance/compatibility source. The maintained runtime no longer needs to use those builders for optional component refreshes.

This creates a clean path for a later compatibility-wrapper reduction without changing the canonical application surface.

## Validation

No local test suite was executed in this environment. CI remains the authoritative validation path.
