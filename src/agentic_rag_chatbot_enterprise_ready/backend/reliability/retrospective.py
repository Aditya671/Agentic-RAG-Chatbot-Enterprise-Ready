"""Deterministic post-run retrospective and monitoring primitives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ExecutionEvent, ExecutionTrace


@dataclass(frozen=True, slots=True)
class ObservedFact:
    """A fact copied or deterministically counted from the execution trace."""

    fact_id: str
    kind: str
    value: str
    event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrospectiveFinding:
    """A derived conclusion; it is never presented as execution evidence."""

    finding_id: str
    category: str
    severity: str
    impact: str
    summary: str
    supporting_fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrospectiveRecommendation:
    """An explainable action derived from one or more retrospective findings."""

    recommendation_id: str
    finding_ids: tuple[str, ...]
    priority: str
    action: str
    rationale: str


@dataclass(frozen=True, slots=True)
class Retrospective:
    run_id: str
    outcome: str
    event_count: int
    evidence_count: int
    errors: tuple[str, ...]
    observations: tuple[str, ...]
    recommendations: tuple[str, ...]
    observed_facts: tuple[ObservedFact, ...] = ()
    findings: tuple[RetrospectiveFinding, ...] = ()
    recommendation_details: tuple[RetrospectiveRecommendation, ...] = ()


class RetrospectiveEngine:
    """Derive deterministic, explainable findings from recorded execution facts."""

    def analyze(self, trace: ExecutionTrace) -> Retrospective:
        if not isinstance(trace, ExecutionTrace):
            raise TypeError("trace must be an ExecutionTrace")

        events = tuple(trace.events)
        errors = tuple(
            error
            for error in [trace.error, *(_event_error(event) for event in events)]
            if error
        )
        facts = self._facts(trace, events, errors)
        findings: list[RetrospectiveFinding] = []
        recommendations: list[RetrospectiveRecommendation] = []

        def add_finding(category: str, severity: str, impact: str, summary: str, *fact_ids: str) -> str:
            finding_id = f"finding-{len(findings) + 1}"
            findings.append(
                RetrospectiveFinding(finding_id, category, severity, impact, summary, tuple(fact_ids))
            )
            return finding_id

        def add_recommendation(finding_id: str, priority: str, action: str, rationale: str) -> None:
            recommendations.append(
                RetrospectiveRecommendation(
                    f"recommendation-{len(recommendations) + 1}",
                    (finding_id,),
                    priority,
                    action,
                    rationale,
                )
            )

        fact = _fact_id(facts, "errors")
        if fact:
            finding_id = add_finding(
                "execution",
                "high" if trace.outcome == "error" else "medium",
                "run reliability",
                "execution contains recorded errors",
                fact,
            )
            add_recommendation(
                finding_id,
                "high" if trace.outcome == "error" else "medium",
                "inspect the failing lifecycle phase and provider boundary",
                "the recommendation is derived from recorded error facts",
            )

        fact = _fact_id(facts, "missing_evidence")
        if fact:
            finding_id = add_finding(
                "evidence",
                "high" if trace.outcome == "success" else "medium",
                "grounding and provenance confidence",
                "execution produced no recorded evidence",
                fact,
            )
            add_recommendation(
                finding_id,
                "high",
                "record source evidence and provenance before emitting a grounded answer",
                "successful execution without evidence cannot demonstrate its grounding boundary",
            )

        fact = _fact_id(facts, "retrieval_empty")
        if fact:
            finding_id = add_finding(
                "retrieval",
                "medium",
                "answer grounding",
                "retrieval completed without recorded results",
                fact,
            )
            add_recommendation(
                finding_id,
                "medium",
                "review retrieval filters, query construction, and corpus coverage",
                "an empty retrieval result is an observed condition, not proof that the corpus is deficient",
            )

        fact = _fact_id(facts, "failed_phases")
        if fact and not _fact_id(facts, "errors"):
            finding_id = add_finding(
                "lifecycle",
                "medium",
                "execution reliability",
                "one or more lifecycle events are marked failed",
                fact,
            )
            add_recommendation(
                finding_id,
                "medium",
                "inspect the failed lifecycle event and its recovery path",
                "failed status is directly recorded by observability instrumentation",
            )

        fact = _fact_id(facts, "missing_response")
        if fact and trace.outcome == "success":
            finding_id = add_finding(
                "response",
                "medium",
                "response completeness",
                "successful execution has no recorded response event",
                fact,
            )
            add_recommendation(
                finding_id,
                "medium",
                "record the response lifecycle event before marking the run successful",
                "the response boundary is part of the observable execution contract",
            )

        observations = tuple(_legacy_observation(fact) for fact in facts)
        if not observations:
            observations = ("execution completed without detected retrospective anomalies",)
        if trace.outcome == "success" and trace.evidence and not findings:
            observations = ("execution completed with recorded evidence and no detected anomalies",)

        recommendation_text = tuple(item.action for item in recommendations)
        return Retrospective(
            trace.run_id,
            trace.outcome,
            len(events),
            len(trace.evidence),
            errors,
            observations,
            recommendation_text,
            tuple(facts),
            tuple(findings),
            tuple(recommendations),
        )

    @staticmethod
    def _facts(
        trace: ExecutionTrace,
        events: tuple[ExecutionEvent, ...],
        errors: tuple[str, ...],
    ) -> list[ObservedFact]:
        facts: list[ObservedFact] = []
        if errors:
            facts.append(ObservedFact("errors", "error", "; ".join(errors)))

        failed = tuple(event for event in events if event.status in {"error", "failed"})
        if failed:
            facts.append(
                ObservedFact(
                    "failed_phases",
                    "failed_phases",
                    ", ".join(event.phase for event in failed),
                    tuple(event.event_id for event in failed),
                )
            )

        if not trace.evidence:
            facts.append(ObservedFact("missing_evidence", "evidence_count", "0"))

        empty_retrievals = tuple(
            event
            for event in events
            if event.phase == "retrieval" and event.attributes.get("result_count") == 0
        )
        if empty_retrievals:
            facts.append(
                ObservedFact(
                    "retrieval_empty",
                    "retrieval_result_count",
                    "0",
                    tuple(event.event_id for event in empty_retrievals),
                )
            )

        has_response = any(event.phase == "response" for event in events)
        if not has_response:
            facts.append(ObservedFact("missing_response", "response_event", "absent"))

        return facts


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    total_runs: int
    successful_runs: int
    failed_runs: int
    error_rate: float
    evidence_coverage: float


class MonitoringEngine:
    """Compute operational health from traces without binding to a telemetry vendor."""

    def snapshot(self, traces: list[ExecutionTrace]) -> HealthSnapshot:
        total = len(traces)
        if total == 0:
            return HealthSnapshot(0, 0, 0, 0.0, 0.0)
        successful = sum(trace.outcome == "success" for trace in traces)
        failed = total - successful
        evidence_runs = sum(bool(trace.evidence) for trace in traces)
        return HealthSnapshot(total, successful, failed, failed / total, evidence_runs / total)


def _event_error(event: ExecutionEvent) -> str | None:
    value: Any = event.attributes.get("error")
    if value:
        return str(value)
    if event.status in {"error", "failed"}:
        error_type = event.attributes.get("error_type")
        return str(error_type) if error_type else f"{event.name} ({event.status})"
    return None


def _fact_id(facts: list[ObservedFact], kind: str) -> str | None:
    for fact in facts:
        if fact.kind == kind:
            return fact.fact_id
    return None


def _legacy_observation(fact: ObservedFact) -> str:
    return f"observed {fact.kind}: {fact.value}"
