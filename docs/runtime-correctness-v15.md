# Runtime Correctness — v15

## Scope

This phase tightens the migration boundary around the retained
`agentic_ai_system_upgraded.py` implementation without changing its public
runtime behavior.

## Test boundary

The repository now has a maintained regression suite under `tests/` for pure
behavior retained by the migration runtime. The suite reads the compatibility
source from its repository-relative path and extracts only the class definition,
so the checks do not require Azure credentials or provider initialization.

The older migration-era harness under `src/` is intentionally not part of the
maintained pytest collection. It contains a machine-specific `/mnt/data`
source reference and should not be treated as CI coverage.

## Covered invariants

- timestamp parsing remains timezone-safe;
- conversation ordering does not mutate caller-owned input;
- response text extraction handles nested response/block representations;
- uploaded filenames cannot escape the configured upload root;
- retrieval `top_k` continues to reject non-positive values;
- CSV initialization remains opt-in for the configured structured-data flow;
- plain-text streaming remains a single response chunk rather than a sequence
  of characters.

## Migration status

The canonical application surface remains `backend.orchestration.agentic_ai_system`.
The upgraded implementation is still an internal compatibility source because
`IntegratedAsyncAgenticAiSystem` currently inherits its established behavior.
The next architectural step is to extract the remaining provider/runtime
responsibilities into explicit modules so the compatibility source can become a
thin wrapper and eventually be retired.
