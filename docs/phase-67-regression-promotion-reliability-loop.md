# Phase 67 — Regression Promotion & Reliability Loop

## Purpose

Phase 67 closes the controlled loop between post-run retrospective analysis and the deterministic regression harness.

```text
ExecutionTrace
    ↓
ObservedFact
    ↓
RetrospectiveFinding
    ↓
RegressionProposal
    ↓
ReviewDecision
    ↓
ReviewedRegression
    ↓
ScenarioCatalog
    ↓
Replay
```

The loop is intentionally **governed**. A retrospective does not modify the regression suite by itself, and a recommendation is never treated as evidence that a fix was implemented.

## Provenance contract

A `RegressionProposal` retains:

- `source_run_id` — the execution that produced the retrospective;
- `source_finding_id` — the specific derived finding used to motivate the proposal;
- `source_fact_ids` — the observed facts supporting that finding;
- the deterministic `HarnessCase` that should become the regression scenario;
- the observation and recommendation presented for review.

This creates an auditable chain back to the operational record without copying raw prompts, model responses, tool payloads, or other telemetry content into the promotion artifact.

For older callers that only have legacy retrospective strings, the existing proposal API remains supported. New integrations should provide or select a structured finding.

## Review gate

Promotion has two distinct operations:

1. `review()` records who reviewed the proposal, whether it was approved, and why.
2. `promote()` adds the exact reviewed `HarnessCase` to the regression catalog.

An unapproved proposal raises `PermissionError` and cannot enter the catalog. A review decision must reference the same proposal id as the proposal being promoted.

The review record is therefore a governance boundary, not a decorative metadata field.

## Why proposals do not become evidence

The reliability model distinguishes four layers:

| Layer | Meaning |
| --- | --- |
| Evidence | Source-backed material captured during execution |
| Observed fact | Execution information directly recorded or counted from the trace |
| Finding | Deterministic interpretation of observed facts |
| Regression proposal | A proposed test derived from a finding |

A regression proposal is a **test-design artifact**. Its presence does not prove that the original failure is reproducible, that the proposed case is correct, or that a remediation has succeeded. Those questions require replay/evaluation.

## Deterministic behavior

Phase 67 deliberately does not introduce:

- LLM-generated regression cases;
- automatic promotion;
- automatic remediation;
- hidden quality scores;
- external telemetry dependencies;
- automatic acceptance of recommendations as evidence.

The exact `HarnessCase` supplied to the proposal is the case that gets promoted after approval. This prevents a promotion step from silently changing the test semantics.

## Example workflow

```python
retrospective = RetrospectiveEngine().analyze(trace)

proposal = RegressionPromotionEngine.propose(
    retrospective,
    case,
    proposal_id="proposal-42",
    finding_id="finding-1",
)

reviewed = RegressionPromotionEngine.review(
    proposal,
    reviewer="engineer",
    approved=True,
    rationale="Reproduced locally and worth protecting with a regression.",
)

RegressionPromotionEngine.promote(reviewed, regression_catalog)
```

After promotion, the normal deterministic harness can replay the scenario. A future phase can use replay outcomes to establish whether the regression is actually fixed or remains present.

## Validation

Focused tests cover:

- finding-to-proposal provenance;
- source observed-fact preservation;
- invalid finding rejection;
- explicit approval gating;
- exact case promotion;
- review identity/rationale requirements;
- backwards-compatible proposal construction.

Repository-local dependency/CI execution is not claimed where the environment cannot provide a reliable execution path.

## Exit criterion

A retrospective finding can become a durable regression scenario only through an explicit, traceable review decision, with provenance preserved from run → finding → proposal → review → promoted case.

## Next phase

Phase 68 moves beyond the reliability workbench toward the complete real application layer, using the established observability, evaluation, benchmarking, retrospective, and governed regression loop as its engineering foundation.
