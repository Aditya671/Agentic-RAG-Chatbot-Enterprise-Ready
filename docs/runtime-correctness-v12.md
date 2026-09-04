# Runtime correctness — Phase 12

## Canonical runtime convergence

Phase 12 makes the converged `IntegratedAsyncAgenticAiSystem` the implementation
behind the historical `backend.orchestration.agentic_ai_system.AsyncAgenticAiSystem`
import path.

This preserves existing callers while ensuring they receive the runtime that
already uses `RetrievalConfig`, provider-boundary retrieval construction,
stable response contracts, and the structured-query adapter.

### Compatibility boundary

The canonical class keeps the existing `upload_and_index_files()` Chainlit
wrapper. Its input/output contract is unchanged; only the underlying runtime
implementation has been converged.

### Migration state

`agentic_ai_system_upgraded.py` remains available as the compatibility source
for the integrated implementation and for focused regression tests. New
application code should import `AsyncAgenticAiSystem` from the canonical
compatibility module rather than importing the upgraded implementation
internals directly.

## Validation

The Phase 12 regression test verifies that the canonical class inherits the
converged runtime and that the historical upload contract remains present.
The test is source-level and does not require Azure credentials or model
services.
