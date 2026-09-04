# Runtime Correctness — Phase 21

## Remove external code execution

The application no longer supports E2B or any remote sandbox/code-interpreter capability.

### Runtime policy

The supported agent capabilities are retrieval, uploaded-file indexing, internet search, optional GraphRAG, and structured CSV analysis. Arbitrary Python execution is intentionally outside the product boundary.

### Removed

- E2B sandbox/code-interpreter runtime integration.
- Coding-assistant runtime configuration and agent tool registration.
- E2B-specific tests and upgrade-report documentation.
- E2B references from architecture/package planning documentation.

### Rationale

Remote code execution introduces an external paid execution dependency and an unnecessary execution surface for the current product. Removing it makes the runtime smaller, easier to operate, and clearer about what the agent is permitted to do.

### Validation

No local test suite was executed in this environment. CI remains the authoritative validation path.
