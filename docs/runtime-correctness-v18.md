# Runtime Correctness — Phase 18

## Optional runtime component factories

Phase 18 introduces a provider-facing factory boundary for the runtime's optional components: reranking, GraphRAG, and isolated code execution.

The boundary is intentionally small and dependency-aware:

`Runtime Orchestration → Runtime Component Factories → Provider Components`

### What changed

- `runtime_components.py` owns construction of the optional reranker, GraphRAG system, and code interpreter.
- Disabled components return `None` without constructing provider clients.
- Reranker depth remains bounded by the active retrieval depth and the existing maximum of five candidates.
- Provider initialization failures retain the existing resilient behavior by returning `None`.
- The factories are exposed through the orchestration package for the next runtime convergence step.
- Dependency-isolated tests cover disabled components and reranker depth behavior.

### Migration intent

The large `agentic_ai_system_upgraded.py` compatibility implementation still contains the historical private builders. They are not removed in this phase because they are part of the compatibility inheritance source.

The next convergence step can route the maintained runtime's component refresh path through these factories, after which the legacy private builders can be reduced to compatibility-only implementations and eventually retired.

## Validation

No local test suite was executed in this environment. CI remains the authoritative validation path.
