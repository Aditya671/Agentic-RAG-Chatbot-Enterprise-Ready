# Runtime Correctness — Phase 24

## Remove obsolete PandasAI execution surface

The repository no longer needs the historical PandasAI CSV adapter. The active
runtime already uses the isolated structured-query boundary backed by
LlamaIndex's configured CSV query engine.

PandasAI was therefore removed rather than carried forward as another optional
execution path. This is intentional: dataframe-agent libraries that generate
and execute code introduce a separate code-execution boundary and would weaken
the runtime simplification achieved by removing the remote sandbox capability.

### Removed

- `backend/orchestration/pandasai_system.py`
- `backend/orchestration/pandasai_system_upgraded.py`
- the PandasAI migration-era regression suite
- the PandasAI upgrade report

### Result

Structured CSV analysis has one maintained application boundary rather than
parallel PandasAI and LlamaIndex implementations. The supported agent runtime
continues to expose structured CSV analysis without introducing arbitrary
Python execution into the application process.

### Verification boundary

No local test suite was executed in this session. CI remains authoritative.
The maintained structured-query regression coverage is the relevant test
surface; live Azure/OpenAI integration remains deployment validation.
