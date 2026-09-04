# Runtime correctness — Phase 27

## Orchestration surface cleanup

Phase 27 removes a stale provider-facing runtime surface that survived the
previous component-factory migration.

### Removed

- `backend/orchestration/runtime_components.py`
- `tests/test_runtime_components.py`
- `backend/orchestration/agentic_ai_system_upgrade_report.md`
- the public `build_code_interpreter` orchestration export

### Canonical component boundary

Optional reranker and GraphRAG construction now remain behind
`backend/orchestration/component_runtime.py`. The factory layer accepts the
provider initializer and logger as explicit dependencies, so orchestration
does not import provider implementations merely to expose a construction
helper.

The retired code-interpreter capability is not reintroduced. The remaining
compatibility no-op in the component factory exists only for the legacy
inheritance source and does not construct or invoke a sandbox.

## Migration boundary

The large historical `agentic_ai_system_upgraded.py` implementation remains an
internal migration source for behavior that has not yet been extracted. Its
legacy regression suite is no longer duplicated under `src/`; maintained
coverage belongs in the top-level `tests/` boundary.

This phase intentionally does not change the agent execution contract or the
provider implementations themselves.

## Verification boundary

No local test suite was executed in this session. CI remains authoritative for
syntax, linting, maintained tests, and package build verification.
