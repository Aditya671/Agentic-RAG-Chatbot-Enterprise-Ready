"""Operational query surface for recorded agent execution traces."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol

from .contracts import ExecutionEvent, ExecutionTrace
from .retrospective import HealthSnapshot, MonitoringEngine


class TraceStore(Protocol):
    def get(self, run_id: str) -> ExecutionTrace | None: ...

    def recent(self, limit: int = 20) -> list[ExecutionTrace]: ...


@dataclass(frozen=True, slots=True)
class TraceQuery:
    request_id: str | None = None
    session_id: str | None = None
    actor_id: str | None = None
    outcome: str | None = None
    phase: str | None = None
    status: str | None = None
    limit: int = 20


@dataclass(frozen=True, slots=True)
class TraceInspection:
    trace: ExecutionTrace
    total_duration_ms: float | None
    tool_calls: int
    retrieval_calls: int
    model_calls: int
    successful_events: int
    failed_events: int
    error_phases: tuple[str, ...]
    provenance_ids: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class ObservabilityService:
    """Provide bounded trace lookup, inspection, and health summaries."""

    def __init__(self, store: TraceStore, monitoring: MonitoringEngine | None = None) -> None:
        self.store = store
        self.monitoring = monitoring or MonitoringEngine()

    def get_run(self, run_id: str) -> TraceInspection | None:
        trace = self.store.get(run_id)
        return self.inspect(trace) if trace is not None else None

    def search(self, query: TraceQuery | None = None) -> tuple[TraceInspection, ...]:
        query = query or TraceQuery()
        if isinstance(query.limit, bool) or not isinstance(query.limit, int) or query.limit < 1:
            raise ValueError("query.limit must be a positive integer")
        matches: list[TraceInspection] = []
        for trace in self.store.recent(query.limit):
            if query.request_id is not None and trace.request_id != query.request_id:
                continue
            if query.session_id is not None and trace.session_id != query.session_id:
                continue
            if query.actor_id is not None and trace.actor_id != query.actor_id:
                continue
            if query.outcome is not None and trace.outcome != query.outcome:
                continue
            if query.phase is not None and not any(event.phase == query.phase for event in trace.events):
                continue
            if query.status is not None and not any(event.status == query.status for event in trace.events):
                continue
            matches.append(self.inspect(trace))
        return tuple(matches)

    def health(self, limit: int = 100) -> HealthSnapshot:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        return self.monitoring.snapshot(self.store.recent(limit))

    @staticmethod
    def inspect(trace: ExecutionTrace) -> TraceInspection:
        if not isinstance(trace, ExecutionTrace):
            raise TypeError("trace must be an ExecutionTrace")
        return TraceInspection(
            trace=trace,
            total_duration_ms=_duration_ms(trace),
            tool_calls=sum(event.phase == "tool" for event in trace.events),
            retrieval_calls=sum(event.phase == "retrieval" for event in trace.events),
            model_calls=sum(event.phase == "model" for event in trace.events),
            successful_events=sum(event.status == "success" for event in trace.events),
            failed_events=sum(event.status == "error" for event in trace.events),
            error_phases=tuple(event.phase for event in trace.events if event.status == "error"),
            provenance_ids=tuple(record.provenance.record_id for record in trace.evidence),
        )


def _duration_ms(trace: ExecutionTrace) -> float | None:
    if not trace.started_at or not trace.finished_at:
        return None
    try:
        started = datetime.fromisoformat(trace.started_at)
        finished = datetime.fromisoformat(trace.finished_at)
    except ValueError:
        return None
    return max(0.0, (finished - started).total_seconds() * 1000)
