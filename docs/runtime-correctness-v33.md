# Runtime Correctness v33 — Protected Retrieval Policy

## Purpose

The retrieval contract is now authoritative for the two parameters that define
retrieval policy:

- `similarity_top_k`
- `vector_store_query_mode`

The provider boundary translates those values into the provider representation.
It must not allow downstream callers to replace them with unvalidated values.

## Ownership

The maintained path is:

`RetrievalConfig → AgentRuntimeBoundary → IntegratedAsyncAgenticAiSystem → provider_boundaries.build_retriever() → index.as_retriever()`

`provider_boundaries.build_retriever()` may still accept provider-specific
options such as `node_postprocessors`, but attempts to override the two policy
keys are rejected explicitly.

## Why this matters

Previously, `build_retriever()` merged arbitrary keyword arguments after the
validated `RetrievalConfig`. That meant a caller could pass a different
`similarity_top_k` or query mode and silently bypass the application contract.

The provider edge is now a one-way translation boundary: application policy is
validated upstream and translated here, while provider-specific options remain
extensible without weakening that policy.

## Validation

Focused provider-boundary tests cover:

- translation of validated retrieval policy;
- preservation of legitimate provider-specific options; and
- rejection of individual or combined policy overrides.

Full repository CI remains authoritative for integration, lint, and build
verification.
