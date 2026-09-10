"""Retention-aware wrappers for existing durable reliability stores."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from .contracts import ExecutionTrace
from .security_audit import SecurityAuditEvent
from .telemetry_policy import TelemetryRetentionPolicy


class RetainedTraceStore:
    """Apply retention policy around an existing trace store without replacing it."""

    def __init__(self, store, *, policy: TelemetryRetentionPolicy | None = None) -> None:
        if store is None:
            raise ValueError("store is required")
        self.store = store
        self.policy = policy or TelemetryRetentionPolicy()

    def save(self, trace: ExecutionTrace) -> None:
        self.store.save(trace)

    def get(self, run_id: str):
        return self.store.get(run_id)

    def recent(self, limit: int = 20):
        return self.store.recent(limit)

    def __iter__(self) -> Iterable[ExecutionTrace]:
        return iter(self.store)


class RetainedAuditSink:
    """Apply an explicit audit-retention policy around an existing audit sink."""

    def __init__(self, sink, *, policy: TelemetryRetentionPolicy | None = None) -> None:
        if sink is None:
            raise ValueError("sink is required")
        self.sink = sink
        self.policy = policy or TelemetryRetentionPolicy()

    def record(self, event: SecurityAuditEvent) -> None:
        self.sink.record(event)

    def recent(self, limit: int = 100):
        return self.sink.recent(limit)

    def retained(self, *, now: datetime | None = None) -> list[SecurityAuditEvent]:
        current = now or datetime.now(UTC)
        cutoff = current - timedelta(days=self.policy.audit_retention_days)
        return [event for event in self.sink.recent(self.policy.max_audit_records)
                if self._parse(event.created_at) >= cutoff][: self.policy.max_audit_records]

    @staticmethod
    def _parse(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
