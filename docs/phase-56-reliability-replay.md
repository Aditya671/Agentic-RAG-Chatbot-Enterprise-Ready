# Phase 56 — Reliability Scenario Replay

Phase 56 extends the reliability foundation with a deterministic scenario catalog and replay API.

## What changed

- Added `ScenarioCatalog` as a named registry of immutable `HarnessCase` definitions.
- Added `HarnessEngine.replay()` for replaying one named scenario.
- Added `HarnessEngine.replay_all()` for deterministic registration-order regression runs.
- Exported the catalog and observability facade from the reliability package.
- Added regression coverage for ordering and successful replay.

## Why this matters

A harness becomes useful for engineering only when a known scenario can be rerun consistently. The catalog separates scenario definition from execution, while the executor remains an injected callable. This keeps provider SDKs, credentials, network access, and model choice outside the deterministic harness contract.

Replay creates the next seam for:

1. persisted scenario catalogs;
2. captured execution fixtures;
3. retrieval/grounding assertions;
4. latency and cost budgets;
5. failure/recovery cases;
6. CI regression gates;
7. retrospective findings promoted to reviewed regression cases.

## Boundary

Replay does not automatically modify prompts, tools, models, policies, or production configuration. A failed scenario produces evidence for engineering review; it is not an autonomous self-healing mechanism.

## Next

The next reliability layer should move beyond an in-memory trace store toward a durable persistence contract, while preserving deterministic replay and keeping sensitive payloads out of telemetry.
