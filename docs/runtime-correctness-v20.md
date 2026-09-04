# Runtime Correctness — Phase 20

## Canonical LLM and embedding loader

Phase 20 moves the maintained LLM/embedding implementation to the canonical `backend.orchestration.llm_loader` module.

The historical `llm_loader_upgraded.py` path remains available as a compatibility re-export, but it is no longer the implementation source of truth.

### Boundary

`Runtime → backend.orchestration.llm_loader → LlamaIndex/OpenAI/Azure OpenAI`

### Preserved behavior

- Azure OpenAI remains the default provider.
- Microsoft Entra ID/default credentials and API-key authentication remain supported.
- Non-Azure OpenAI loading remains supported.
- Key Vault and environment-variable credential resolution remain supported.
- Temperature and timeout validation remain explicit.
- Deployment-name overrides remain supported.
- O4-mini-high reasoning behavior remains preserved.
- Embedding configuration continues to come from the index configuration.

### Migration intent

The upgraded module path is retained only for compatibility. New runtime code should import from the canonical loader path. This removes another `*_upgraded.py` implementation from the maintained architecture without forcing an import-path migration on existing callers.

## Validation

No local test suite was executed in this environment. CI remains the authoritative validation path.
