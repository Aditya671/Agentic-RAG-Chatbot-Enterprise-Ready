# Runtime Correctness — v16

## Scope

This phase introduces a shared, provider-neutral retrieval-policy validator and
makes the converged runtime use it before constructing its `RetrievalConfig`.

## Retrieval policy boundary

`runtime_policy.validate_top_k()` is now the single validation rule for
`similarity_top_k` on the maintained runtime path. It deliberately rejects
booleans, strings, floats, `None`, and non-positive integers instead of silently
coercing values.

The provider-neutral policy remains separate from LlamaIndex translation:

`Runtime Policy → RetrievalConfig → Provider Boundary → LlamaIndex`

## Compatibility

The legacy `agentic_ai_system_upgraded.py` implementation remains an inheritance
source for the integrated runtime. The converged subclass now overrides its
`_validate_top_k` boundary, so the maintained application path does not inherit
the legacy coercion behavior.

This is an incremental extraction step rather than a wholesale rewrite. The
remaining provider/runtime methods can now be moved behind explicit boundaries
without changing the canonical application import path.

## Validation

The new policy tests are dependency-light and cover valid integers, booleans,
other non-integer values, zero, and negative values. No local test suite was
executed in this environment; CI remains the authoritative execution boundary.
