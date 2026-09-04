"""Deterministic evaluation metrics over recorded reliability traces."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from .contracts import ExecutionTrace


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Aggregate evaluation result for a trace collection."""

    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    evidence_coverage: float
    average_latency_ms: float
    error_rate: float


class EvaluationEngine:
    """Compute explainable, provider-neutral metrics from execution traces."""

    @staticmethod
    def evaluate(traces: Iterable[ExecutionTrace]) -> EvaluationResult:
        items = list(traces)
        if any(not isinstance(trace, ExecutionTrace) for trace in items):
            raise TypeError("traces must contain ExecutionTrace instances")
        total = len(items)
        successful = sum(trace.outcome == "success" for trace in items)
        failed = sum(trace.outcome in {"error", "failure"} for trace in items)
        completed = [trace for trace in items if trace.finished_at and trace.started_at]
        latency_values = [EvaluationEngine._duration_ms(trace) for trace in completed]
        with_evidence = sum(bool(trace.evidence) for trace in items)
        return EvaluationResult(
            total_runs=total,
            successful_runs=successful,
            failed_runs=failed,
            success_rate=successful / total if total else 0.0,
            evidence_coverage=with_evidence / total if total else 0.0,
            average_latency_ms=mean(latency_values) if latency_values else 0.0,
            error_rate=sum(trace.outcome == "error" for trace in items) / total if total else 0.0,
        )

    @staticmethod
    def _duration_ms(trace: ExecutionTrace) -> float:
        """Return duration using the trace timestamps, or zero when unparsable."""
        from datetime import datetime

        try:
            started = datetime.fromisoformat(trace.started_at.replace("Z", "+00:00"))
            finished = datetime.fromisoformat(trace.finished_at.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            return 0.0
        return max(0.0, (finished - started).total_seconds() * 1000)
