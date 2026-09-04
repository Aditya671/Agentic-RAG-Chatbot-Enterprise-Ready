# Phase 61 — Claim ↔ Evidence Grounding

## Purpose

Phase 59 established scenario-level evidence identity and retrieval relevance. Phase 60 established a reviewed path from retrospective findings into regression scenarios. Phase 61 adds an explicit claim-to-evidence relationship layer so grounding can be evaluated at the claim level without asking an LLM to judge its own answer.

## Contracts

- `Claim` represents an explicit response claim and optional required evidence source IDs.
- `ClaimEvidenceLink` records an explicit `supports`, `contradicts`, or `contextual` relationship.
- `GroundingResult` reports deterministic claim coverage and failures.
- `ClaimGroundingEvaluator` evaluates only supplied claims, links, and evidence records.

## Evaluation semantics

A claim is counted as supported when:

1. every required evidence source ID has an explicit `supports` link;
2. a claim with no required IDs has at least one explicit support link; and
3. the claim has no explicit `contradicts` link to available evidence.

Links to evidence that was not recorded in the execution are reported as failures. Links to unknown claims are rejected as invalid input.

`claim_coverage` is therefore a deterministic relationship-coverage metric. It is **not** semantic entailment, factual truth, or an LLM judgement of whether an excerpt proves the claim.

## Architecture boundary

The evaluator does not parse answer prose to invent claims or citations. Claims and relationships must be produced explicitly by a caller or future structured response contract. This keeps the reliability layer auditable and prevents unsupported citations from being inferred after the fact.

## Reliability loop

The current progression is:

**Observe → Understand → Propose → Review → Promote → Replay → Ground**

Future work can connect structured claim output from the agent response contract to this evaluator, then add aggregate grounding metrics and reviewed grounding failures to the regression catalog.
