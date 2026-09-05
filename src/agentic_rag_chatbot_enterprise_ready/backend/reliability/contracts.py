"""Serializable contracts shared by observability, evidence, and evaluation."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class Evidence:
    source_id: str
    source_type: str
    locator: str | None = None
    content_hash: str | None = None
    excerpt: str | None = None
    retrieved_at: str = field(default_factory=utc_now)
    relevance: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    record_id: str
    parent_ids: tuple[str, ...] = ()
    operation: str = "unknown"
    actor: str = "agent"
    provider: str | None = None
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence: Evidence
    provenance: ProvenanceRecord


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    name: str
    phase: str
    status: str = "started"
    run_id: str = ""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utc_now)
    duration_ms: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionTrace:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    events: list[ExecutionEvent] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    outcome: str = "running"
    error: str | None = None

    def add_event(self, event: ExecutionEvent) -> None:
        if event.run_id and event.run_id != self.run_id:
            raise ValueError("event belongs to a different execution run")
        self.events.append(event)

    def add_evidence(self, record: EvidenceRecord) -> None:
        self.evidence.append(record)

    def finish(self, outcome: str = "success", error: str | None = None) -> None:
        self.outcome = outcome
        self.error = error
        self.finished_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
