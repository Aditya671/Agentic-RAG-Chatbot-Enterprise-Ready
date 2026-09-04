# Runtime Correctness — Phase 29

## Orchestration ownership

The large historical orchestration implementation has been moved behind an
explicit internal runtime module:

```text
agentic_ai_system.py
        ↓
integrated_agent_system.py
        ↓
agentic_ai_system_runtime.py
```

The public `agentic_ai_system.py` surface remains stable, including the
Chainlit upload wrapper. `agentic_ai_system_upgraded.py` is now compatibility-only
and no longer owns a second implementation.

## Why this boundary exists

The repository had accumulated a large `*_upgraded.py` orchestration module
that was still the actual inheritance source. Earlier phases established
provider and runtime boundaries, but the filename continued to imply that the
migration implementation was the production owner.

Phase 29 removes that ambiguity without changing the orchestration behavior in
one large rewrite. The implementation is relocated to an explicitly internal
runtime module; public and historical import paths remain stable.

## Preserved behavior

- model, embedding, memory, and conversation-thread lifecycle
- Azure credential ownership
- vector-index initialization
- background upload/indexing contract
- reranker and GraphRAG integration
- structured CSV integration
- response and streaming behavior
- public `AsyncAgenticAiSystem` import surface

## Next cleanup boundary

The relocated runtime still contains historical capability/configuration code
that should be simplified separately. In particular, retired code-execution
references must be removed from the internal runtime rather than mixed into
this ownership migration.

## Verification

No local test suite was executed in this session. CI remains authoritative for
syntax, linting, maintained tests, and package build verification.
