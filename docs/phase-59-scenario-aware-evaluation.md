# Phase 59 — Scenario-Aware Retrieval and Evidence Evaluation

Phase 59 extends the deterministic harness so a regression scenario can assert not only what the agent answered, but also what evidence it retrieved.

## Implemented

- `HarnessCase.expected_evidence_source_ids` declares the evidence expected for a scenario.
- `HarnessCase.min_evidence_relevance` can enforce a deterministic retrieval-quality floor.
- Harness executors may return explicit `Evidence` records alongside the response.
- `ScenarioEvaluationEngine` measures expected-evidence coverage and mean recorded relevance.
- `HarnessResult` exposes `grounding_coverage` and `retrieval_relevance` for regression reporting.
- Existing text and outcome assertions remain unchanged.

## Important boundary

The `grounding_coverage` metric is intentionally conservative: it measures whether the expected evidence identities were present in the recorded retrieval result. It does **not** claim that an answer is semantically entailed by those documents. Semantic grounding evaluation is a later, explicitly defined evaluator and must not be smuggled into a metric merely because evidence exists.

Likewise, retrieval relevance is based only on relevance values already emitted by the retrieval/evidence boundary. The evaluator does not invent a second ranking model or ask an LLM to judge retrieval quality.

## Harness contract

A deterministic executor can return:

```python
{
    "response_text": "...",
    "evidence": [
        Evidence("document-1", "document", "page:4", relevance=0.92),
    ],
}
```

A scenario can then require:

```python
HarnessCase(
    "investment-case",
    "What changed in the asset outlook?",
    expected_text_contains=("outlook",),
    expected_evidence_source_ids=("document-1",),
    min_evidence_relevance=0.80,
)
```

## Why this matters

A passing answer-only test can hide retrieval regressions. The response may still contain plausible language while the system retrieves the wrong source, loses a required document, or falls below an agreed relevance floor.

The scenario now has three deterministic layers:

1. **Outcome** — did execution complete as expected?
2. **Answer assertion** — did the response contain required behavior/text?
3. **Evidence assertion** — did retrieval produce the expected evidence with acceptable recorded relevance?

This makes the harness useful for evidence-grounded systems without pretending that deterministic identity checks are equivalent to full semantic evaluation.

## Next

1. Add reviewed retrospective findings as explicit regression scenarios.
2. Add claim/evidence relationships for stronger grounding evaluation.
3. Add monitoring and alert adapters over the existing reliability contracts.
4. Expand provider/cloud contract suites.
