# Runtime Correctness — v35

## Scope

This phase hardens the provider retrieval boundary against malformed query-mode
inputs before any LlamaIndex translation occurs.

## Boundary contract

`resolve_query_mode()` is a provider-edge adapter, but it still owns an explicit
input contract. It now rejects missing, non-string, and whitespace-only values
with a stable `ValueError` instead of allowing an implementation-level
`AttributeError` or provider call to occur.

The maintained flow remains:

`RetrievalConfig → AgentRuntimeBoundary → provider boundary → LlamaIndex`

`RetrievalConfig` remains responsible for application policy validation; the
provider boundary is responsible for validating its own adapter inputs before
performing SDK-specific translation.

## Compatibility

Existing supported aliases remain unchanged. This is an input-hardening change,
not a query-mode policy change.

## Validation

Focused provider-boundary regression coverage now includes invalid input types,
empty strings, and whitespace-only values. Full CI remains authoritative for
repository-wide test, lint, and build verification.
