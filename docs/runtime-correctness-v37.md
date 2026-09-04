# Runtime Correctness — v37

## Scope

This phase aligns the Chainlit retrieval setting with the maintained runtime retrieval contract.

## Contract

The runtime requires `similarity_top_k >= 1`. The frontend previously allowed `0`, which could pass normalization and fail later when the agent was configured.

The frontend now clamps persisted/settings input to `1..30` and exposes the same lower bound in the UI slider.

This keeps the boundary consistent:

`Chainlit settings → normalized top_k (1..30) → runtime validation`

## Compatibility

Existing valid values remain unchanged. Older persisted values of `0` are normalized to `1` rather than causing runtime initialization failure.

No retrieval provider behavior or ranking policy was changed.

## Validation

The change is intentionally limited to frontend normalization and presentation of an already-established backend invariant. Repository CI remains authoritative for full test, lint, and build verification.
