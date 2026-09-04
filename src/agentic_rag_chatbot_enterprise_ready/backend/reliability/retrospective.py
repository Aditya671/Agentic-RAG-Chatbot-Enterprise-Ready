"""Post-run retrospective and monitoring primitives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ExecutionTrace


@dataclass(frozen=True, slots=True)
class Retrospective:
    run_id: str
    outcome: str
    event_count: int
    evidence_count: int
    errors: tuple[str, ...]
    observations: tuple[str, ...]
    recommendations: tuple[str, ...]


class RetrospectiveEngine:
    """Derive explainable operational observations from recorded execution facts."""

    def analyze(self, trace: ExecutionTrace) -> Retrospective:
        errors = tuple(filter(None, [trace.error] + [e.attributes.get("error") for e in trace.events]))
        observations: list[str] = []
        recommendations: list[str] = []
        if not trace.evidence:
            observations.append("execution produced no recorded evidence")
            recommendations.append("record source evidence before emitting grounded answers")
        if errors:
            observations.append("execution contained one or more errors")
            recommendations.append("inspect the failing execution phase and provider boundary")
        if trace.outcome == "success" and trace.evidence:
            observations.append("execution completed with recorded evidence")
        if not observations:
            observations.append("execution completed without recorded anomalies")
        return Retrospective(trace.run_id, trace.outcome, len(trace.events), len(trace.evidence), errors, tuple(observations), tuple(recommendations))


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
