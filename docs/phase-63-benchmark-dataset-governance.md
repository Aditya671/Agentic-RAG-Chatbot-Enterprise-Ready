# Phase 63 — Benchmark Dataset & Scenario Governance

## Purpose

Phase 62 established the execution machinery for comparing agent architectures. Phase 63 makes the benchmark inputs durable and reproducible.

A benchmark result is only meaningful when the inputs that produced it can be identified and reconstructed. Scenario definitions, evidence fixtures, expected grounding relationships, and benchmark configuration therefore become versioned engineering assets.

## Governance model

```text
Dataset
├── dataset identity + version
├── Scenario
│   ├── scenario identity + version
│   ├── question / harness expectations
│   ├── difficulty + tags
│   ├── expected capabilities
│   ├── expected claims
│   ├── expected claim → evidence relationships
│   └── fixture references
└── Evidence Fixture
    ├── fixture identity + version
    ├── immutable EvidenceRecord collection
    └── fixture metadata

BenchmarkConfig
├── benchmark identity + version
├── scenario-set version
└── repetitions
```

## Versioned scenarios

`BenchmarkScenario` wraps the existing deterministic `HarnessCase` with explicit benchmark metadata. The scenario identity is `(scenario_id, version)`.

A scenario can declare:

- difficulty: `basic`, `standard`, `advanced`, `failure`, or `recovery`;
- tags for controlled grouping;
- expected capabilities such as retrieval or grounding;
- fixture IDs that define the evidence available to the scenario;
- expected claims and their required evidence;
- expected claim/evidence relationships;
- arbitrary descriptive metadata.

The underlying `HarnessCase` remains the source of deterministic response/evidence assertions rather than being replaced by a second assertion mechanism.

## Evidence fixtures

`BenchmarkEvidenceFixture` is an immutable, versioned collection of `EvidenceRecord` objects.

This creates an explicit evidence boundary:

```text
scenario → fixture reference → evidence records
```

Benchmark architectures should consume only the evidence made available by the benchmark dataset. Fixtures are not generated during an individual architecture run, which prevents one architecture from silently receiving different benchmark inputs.

Fixture identity is `(fixture_id, version)`. A changed fixture should receive a new version rather than silently mutating historical benchmark inputs.

## Expected claims and evidence relationships

Scenarios may declare `Claim` and `ClaimEvidenceLink` expectations. This keeps benchmark grounding requirements explicit and machine-readable.

For example:

```text
Claim: "Revenue increased."
Required evidence: annual-report
Relationship: claim-1 --supports--> annual-report
```

These relationships describe the benchmark expectation. They do not claim that the benchmark has performed semantic entailment. The existing deterministic grounding evaluator remains responsible for measuring explicit relationship coverage.

## Dataset boundary

`BenchmarkDataset` binds scenarios to the fixture IDs they reference.

Construction rejects:

- duplicate scenario/version identities;
- duplicate fixture/version identities;
- scenario references to unknown fixtures;
- invalid scenario or fixture types.

This makes the dataset a self-contained input boundary rather than a loose collection of test helpers.

## Benchmark configuration identity

`BenchmarkConfig` identifies the execution configuration independently of the scenario implementation:

```text
<benchmark_id>@<version>::scenarios@<scenario_set_version>
```

Repetitions are part of the configuration and must be at least one.

A benchmark result can therefore record both:

```text
scenario: revenue-001@1.0
configuration: architecture-comparison@1.0::scenarios@2026.09
```

without relying on undocumented local state.

## Failure and recovery scenarios

Failure and recovery are represented as first-class scenario difficulty categories. They should be added using deterministic fixtures and explicit expected outcomes rather than simulated failures hidden inside architecture-specific code.

Examples of suitable future scenarios include:

- unavailable evidence source;
- malformed tool response;
- retrieval returning irrelevant evidence;
- transient execution failure with a bounded recovery path;
- grounded answer after a failed first retrieval attempt.

The scenario should define the observable expectation; the architecture adapter should not redefine the benchmark's success criteria.

## Historical comparisons

Versioning is deliberately append-oriented. When a benchmark input changes materially:

1. create a new scenario or fixture version;
2. update the dataset version when the scenario set changes;
3. update benchmark configuration identity when the benchmark definition changes;
4. retain the old identity for historical comparisons.

This prevents a benchmark result from becoming impossible to interpret because its inputs were silently overwritten.

## Reproducibility target

Phase 63 is complete when a benchmark run can be reconstructed from named, versioned assets:

```text
benchmark configuration
        +
scenario/version
        +
fixture/version
        +
architecture implementation/version
        ↓
reproducible benchmark execution
```

The goal is not to build a large dataset-management platform. The goal is to establish a small, explicit contract that makes benchmark inputs auditable and reproducible before Phase 64 adds reporting and comparison workflows.
