# Phase 64 — Benchmark Reporting & Architecture Comparison

## Purpose

Phase 63 made benchmark inputs versioned and reproducible. Phase 64 turns the execution records into deterministic reports that engineers can inspect and compare.

The reporting layer must explain trade-offs rather than manufacture a single winner.

## Reporting model

```text
Benchmark runs
      ↓
per-architecture aggregates
      ↓
pairwise metric deltas
      ↓
engineering comparison
```

`BenchmarkReporter` builds a `BenchmarkReport` from the existing `ArchitectureBenchmarkRun` records. It reuses the Phase 62 aggregate calculations rather than creating a second metric implementation.

## Report contents

A report contains:

- raw scenario/architecture run metrics;
- per-architecture aggregate metrics;
- pairwise architecture comparisons;
- pass-rate deltas;
- grounding and retrieval deltas;
- latency deltas;
- model/tool/retrieval activity deltas;
- token and estimated-cost deltas where telemetry exists;
- error-rate deltas;
- provenance-completeness deltas;
- repeatability deltas.

## Comparison semantics

A comparison is directional:

```text
candidate metric − baseline metric
```

Therefore a negative latency delta is an improvement, while a positive pass-rate delta is an improvement. The report deliberately does not normalize these into one score because different engineering goals can legitimately prioritize different dimensions.

Example:

```text
Direct RAG → Agentic RAG
pass rate:       +0.25
latency:        -50 ms
model calls:     +1
estimated cost:  +$0.01
```

The engineer can see the trade-off instead of being told that one architecture is universally better.

## No hidden winner

The reporter does not:

- assign a composite architecture score;
- infer a preferred architecture from metric weights;
- use an LLM to judge which architecture won;
- replace deterministic benchmark metrics with qualitative claims.

A future product-facing comparison view may highlight meaningful improvements, regressions, or trade-offs, but those interpretations must remain traceable to the underlying metrics.

## Regressions and baselines

Phase 64 establishes the comparison primitives needed for baseline deltas. Baseline selection itself should remain explicit rather than silently choosing the first or newest architecture.

A later workflow can associate a named baseline architecture/configuration with a benchmark run and report regressions against it.

## Relationship to Phase 63

Reporting is meaningful only when the input identity is known. A production benchmark report should therefore be associated with:

```text
benchmark configuration
+ dataset/scenario version
+ fixture versions
+ architecture implementation/version
+ execution metrics
```

Phase 64 does not duplicate dataset governance or execution logic; it consumes those contracts.

## Validation target

The reporting layer is complete when deterministic benchmark results can be transformed into a serializable report and engineers can inspect architecture-to-architecture metric deltas without relying on hidden scoring or model-generated judgement.

Phase 65 can then focus on making the execution trace and benchmark information operationally inspectable through a coherent observability surface.
