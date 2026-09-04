# Phase 60 — Reviewed Retrospective Findings → Regression Scenarios

## Purpose

Phase 55 introduced deterministic retrospectives: the system derives observations and recommendations from recorded execution facts rather than asking an LLM to explain its own behavior. Phase 56 introduced a deterministic scenario catalog and replay path. Phase 59 added evidence-aware assertions.

The missing control point was promotion: a retrospective finding should be able to become a regression scenario, but it must not silently rewrite the test suite.

Phase 60 adds an explicit, auditable review gate between those two capabilities.

## Flow

```text
ExecutionTrace
    ↓
RetrospectiveEngine
    ↓
Retrospective
    ↓
RegressionPromotionEngine.propose()
    ↓
RegressionProposal
    ↓
Human review
    ↓
ReviewDecision
    ↓
ReviewedRegression
    ↓ (only when approved)
ScenarioCatalog.add()
    ↓
HarnessEngine.replay()
```

## Contracts

### `RegressionProposal`

A proposal records:

- a stable proposal ID
- the retrospective run ID that motivated it
- the selected observation
- the selected recommendation
- the exact `HarnessCase` proposed for regression coverage
- creation time

The proposal does not mutate the catalog.

### `ReviewDecision`

A decision records:

- proposal ID
- reviewer identity
- approval state
- rationale
- review timestamp

Reviewer and rationale are required so approval is an auditable action rather than a boolean with no context.

### `ReviewedRegression`

This object binds the proposal and its review decision together. Promotion verifies that the decision references the same proposal and rejects unapproved decisions.

## Safety boundary

This phase intentionally does **not** implement autonomous test generation or automatic self-modification.

The retrospective engine may identify a useful failure pattern. A caller supplies the concrete regression case, a human reviews that proposal, and only an approved proposal can enter `ScenarioCatalog`.

This keeps the improvement loop:

**observe → understand → propose → review → promote → replay**

rather than:

**observe → modify production tests automatically**

That distinction matters because not every production failure is a product defect. External outages, provider incidents, malformed third-party data, intentional behavior changes, or obsolete expectations may be inappropriate as permanent regression cases.

## Determinism

Promotion preserves the exact `HarnessCase` supplied to the proposal. It does not rewrite expectations during approval, and `ScenarioCatalog` retains its existing duplicate-ID protection and registration-order replay semantics.

The review metadata is separate from the executable case so the harness remains simple and deterministic.

## Provider neutrality

No Azure, AWS, GCP, database, telemetry vendor, or model dependency is introduced. The promotion layer operates entirely on reliability contracts and the existing scenario catalog.

## Security

Review metadata must not contain credentials, access tokens, secrets, or uncontrolled sensitive payloads. The source run ID should identify the recorded trace rather than embedding trace contents in the regression proposal.

## Regression coverage

Tests verify that:

1. retrospective facts become an auditable proposal
2. unapproved proposals cannot enter the catalog
3. approved proposals promote the exact proposed case
4. reviewer identity and rationale are required
5. proposal/review identity remains bound

## Next reliability layers

1. strengthen grounding evaluation with explicit claim/evidence relationships
2. add monitoring and alert adapters
3. add provider/cloud contract suites for Azure, AWS, GCP, local, and other infrastructure boundaries
4. connect reviewed regression promotion to persisted review/audit storage when the application has a durable governance boundary
