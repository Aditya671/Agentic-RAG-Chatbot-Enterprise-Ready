# Phase 66 — Agent Retrospective Engine

## Purpose

Phase 66 turns the structured execution facts produced by the reliability and observability layers into a deterministic post-run retrospective. It deliberately keeps three layers separate:

```text
ExecutionTrace
    ↓
ObservedFact
    ↓
RetrospectiveFinding
    ↓
RetrospectiveRecommendation
```

The engine does not use an LLM as a judge and does not rewrite recommendations as evidence.

## What is observed

`ObservedFact` represents information directly recoverable from an `ExecutionTrace`, such as:

- recorded execution errors;
- lifecycle phases marked `error` or `failed`;
- zero recorded evidence;
- retrieval events with `result_count == 0`;
- absence of a response lifecycle event.

Facts can retain supporting event identifiers where the source is an execution event. This makes the retrospective traceable back to the operational record.

## What is derived

`RetrospectiveFinding` is a deterministic interpretation of one or more observed facts. Each finding contains:

- category;
- severity;
- impact;
- concise summary;
- supporting fact identifiers.

A finding is therefore an analysis artifact, not a new evidence record.

## What is recommended

`RetrospectiveRecommendation` contains an explicit action and rationale linked to finding identifiers. Recommendations explain what should be inspected or improved; they do not claim that the recommended action itself occurred.

The legacy `observations` and `recommendations` string fields remain populated for compatibility. New consumers should prefer `observed_facts`, `findings`, and `recommendation_details` when structured analysis is required.

## Deterministic rules in this phase

| Condition | Derived finding | Typical action |
| --- | --- | --- |
| Recorded error | Execution reliability issue | Inspect failing phase/provider boundary |
| No evidence | Evidence/grounding issue | Record source evidence and provenance |
| Retrieval result count is zero | Retrieval issue | Review filters, query construction, corpus coverage |
| Failed lifecycle event without an explicit error fact | Lifecycle issue | Inspect failed event and recovery path |
| Successful run without response event | Response issue | Record response boundary before success |

These rules are intentionally conservative. For example, an empty retrieval result is reported as an observed retrieval condition; the engine does **not** conclude that the corpus is defective.

## Safety and provenance boundary

The retrospective engine consumes `ExecutionTrace` only. It does not accept raw prompts, model responses, tool arguments, or tool results. Existing observability boundaries remain responsible for preventing sensitive payloads from entering telemetry.

The distinction is important:

- **Evidence** answers: “What source-backed record was captured?”
- **Observed fact** answers: “What execution fact was recorded?”
- **Finding** answers: “What deterministic conclusion follows from those facts?”
- **Recommendation** answers: “What action should an engineer consider?”

None of these layers silently promotes a recommendation or finding into evidence.

## Integration with Phase 65

Phase 65 provides the operational inspection surface. A caller can obtain an `ExecutionTrace` directly or through the observability layer and pass it to `RetrospectiveEngine.analyze()`.

This keeps storage, telemetry querying, retrospective reasoning, and future reporting as separate concerns. A future productized retrospective API can therefore add persistence or presentation without changing the underlying execution facts.

## Exit criterion

An engineer can take a structured run and obtain a deterministic retrospective that identifies operational anomalies, links each derived finding to recorded facts, and provides explainable recommendations without introducing an LLM judge or altering the original trace.

## Intentionally out of scope

- LLM-generated retrospective narratives;
- automatic remediation;
- automatic regression promotion;
- hidden health scores or composite “agent quality” scores;
- vendor-specific telemetry integrations;
- changing or mutating the source execution trace.

Those concerns remain separate so that retrospective analysis can be evaluated independently before it is used to drive automated decisions.
