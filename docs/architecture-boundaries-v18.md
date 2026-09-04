# Architecture Boundary Map — Phase 18

The runtime is being converged from the historical monolithic implementation toward explicit seams.

## Current maintained boundaries

- Retrieval policy → `runtime_policy.py`
- Retrieval provider translation → `provider_boundaries.py`
- Agent tool construction → `tool_factory.py`
- Structured CSV construction → `structured_csv_runtime.py`
- Optional component construction → `runtime_components.py`
- Response normalization → `execution_contract.py`
- Runtime response/stream boundary → `runtime_boundary.py`

## Compatibility source

`agentic_ai_system_upgraded.py` remains the inheritance source for behavior that has not yet been extracted. It is deliberately excluded from the normal Ruff scope while the migration is in progress.

The objective is not to duplicate the runtime indefinitely. Each boundary should replace one responsibility in the maintained path, followed by removal or reduction of the corresponding compatibility implementation once callers no longer depend on it.
