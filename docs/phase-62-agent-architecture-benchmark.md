# Phase 62 — Agent Architecture Benchmark

**Status:** Implemented foundation

## Objective

Compare agent architectures under controlled conditions rather than comparing isolated demos.

For a benchmark run, every architecture receives the same scenario, available evidence, and scenario evaluation rules. The benchmark records execution facts and produces comparable metrics.

## Architecture contract

An architecture implements `ArchitectureAdapter` and exposes an `ArchitectureSpec` containing:

- stable architecture id;
- version/configuration identity;
- human-readable description.

The adapter receives an immutable `BenchmarkContext` containing the `HarnessCase` and the evidence fixture available to the run.

This keeps architecture choice separate from scenario definition and evaluation.

## Controlled dimensions

The benchmark records:

- scenario pass/fail;
- claim/evidence grounding coverage from the existing scenario evaluator;
- retrieval relevance;
- latency;
- model-call count;
- tool-call count;
- retrieval-call count;
- input/output token counts when supplied by model telemetry;
- estimated model cost when supplied by model telemetry;
- execution error rate;
- provenance completeness;
- response repeatability across repeated runs.

Metrics are derived from execution facts. The benchmark does not ask an agent to grade itself.

## Fairness rules

1. Use the same `HarnessCase` for every architecture.
2. Use the same evidence fixture and evidence availability for every architecture.
3. Use the same scenario assertions and evaluation engine.
4. Keep architecture identity/version explicit.
5. Do not rank architectures using a hidden composite score.
6. Do not treat additional model/tool calls as quality by themselves.
7. Preserve per-scenario results so aggregate numbers cannot hide regressions.
8. Treat optional token/cost telemetry as measurements, not inferred values.

## Example

A benchmark can compare a direct RAG adapter and a tool-aware adapter against the same question and evidence:

```text
Scenario: revenue-by-region-001
Evidence: annual-report-2025, regional-table-01

                    Direct RAG       Tool-aware
Pass                    yes              yes
Grounding              1.00             1.00
Retrieval relevance    0.91             0.94
Model calls              1                3
Tool calls               0                1
Latency                 420ms            910ms
Provenance              1.00             1.00
```

The benchmark deliberately does **not** declare the tool-aware architecture better because its retrieval relevance is higher. Engineers can inspect the trade-off: both passed and were fully grounded, while the tool-aware path used more execution steps and higher latency.

## Exit criteria for Phase 62 foundation

- [x] Architecture identity is explicit.
- [x] Multiple architectures can run through one harness.
- [x] Equivalent scenario/evidence inputs are supported.
- [x] Per-run comparable metrics are recorded.
- [x] Architecture-level aggregates are available.
- [x] Optional model token/cost telemetry is captured when explicitly supplied.
- [x] Repeatability can be measured across repetitions.
- [x] No hidden quality score is introduced.
- [x] The benchmark remains provider-neutral.

Phase 63 should make scenarios and benchmark configurations versioned, durable engineering assets. Phase 64 should turn benchmark results into human-readable comparison reports.
