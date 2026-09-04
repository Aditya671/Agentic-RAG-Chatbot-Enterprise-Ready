"""Scenario-aware retrieval and evidence evaluation."""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import ExecutionTrace


@dataclass(frozen=True, slots=True)
class ScenarioEvaluationResult:
    """Deterministic evaluation of a scenario's answer and retrieved evidence."""

    passed: bool
    failures: tuple[str, ...]
    grounding_coverage: float
    retrieval_relevance: float


class ScenarioEvaluationEngine:
    """Evaluate explicit scenario expectations without semantic self-judgement."""

    @staticmethod
    def evaluate(case, trace: ExecutionTrace, response_text: str) -> ScenarioEvaluationResult:
        from .harness import HarnessCase

        if not isinstance(case, HarnessCase):
            raise TypeError("case must be a HarnessCase")
        if not isinstance(trace, ExecutionTrace):
            raise TypeError("trace must be an ExecutionTrace")
        if not isinstance(response_text, str):
            raise TypeError("response_text must be a string")

        failures: list[str] = []
        lowered = response_text.casefold()
        failures.extend(
            f"response missing expected text: {expected!r}"
            for expected in case.expected_text_contains
            if expected.casefold() not in lowered
        )

        expected_ids = tuple(dict.fromkeys(case.expected_evidence_source_ids))
        retrieved_ids = {record.evidence.source_id for record in trace.evidence}
        matched_ids = [source_id for source_id in expected_ids if source_id in retrieved_ids]
        grounding_coverage = len(matched_ids) / len(expected_ids) if expected_ids else 1.0

        if expected_ids:
            missing = tuple(source_id for source_id in expected_ids if source_id not in retrieved_ids)
            if missing:
                failures.append(f"missing expected evidence source ids: {missing!r}")

        relevance_values = [
            record.evidence.relevance
            for record in trace.evidence
            if record.evidence.relevance is not None
        ]
        retrieval_relevance = sum(relevance_values) / len(relevance_values) if relevance_values else 0.0
        threshold = case.min_evidence_relevance
        if threshold is not None:
            if not 0.0 <= threshold <= 1.0:
                raise ValueError("case.min_evidence_relevance must be between 0 and 1")
            if not relevance_values or min(relevance_values) < threshold:
                failures.append(f"evidence relevance below required threshold: {threshold}")

        return ScenarioEvaluationResult(
            passed=not failures,
            failures=tuple(failures),
            grounding_coverage=grounding_coverage,
            retrieval_relevance=retrieval_relevance,
        )
