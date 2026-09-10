"""Durable provider-neutral persistence for security audit events."""
from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock

from .security_audit import SecurityAuditEvent


class JsonlSecurityAuditSink:
    """Append-only JSONL security audit sink with bounded retention queries."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        retention_days: int = 90,
        max_events: int = 100_000,
    ) -> None:
        if not path:
            raise ValueError("path must be non-empty")
        if isinstance(retention_days, bool) or not isinstance(retention_days, int) or retention_days < 1:
            raise ValueError("retention_days must be a positive integer")
        if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
            raise ValueError("max_events must be a positive integer")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.max_events = max_events
        self._lock = RLock()

    def record(self, event: SecurityAuditEvent) -> None:
        if not isinstance(event, SecurityAuditEvent):
            raise TypeError("event must be a SecurityAuditEvent")
        payload = json.dumps(
            {
                "event_type": event.event_type,
                "capability": event.capability,
                "outcome": event.outcome,
                "actor_id": event.actor_id,
                "tenant_id": event.tenant_id,
                "reason": event.reason,
                "metadata": dict(event.metadata),
                "created_at": event.created_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self.prune()

    def recent(self, limit: int = 100) -> list[SecurityAuditEvent]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with self._lock:
            events = self._load_events()
            return events[-limit:][::-1]

    def prune(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        cutoff = current - timedelta(days=self.retention_days)
        with self._lock:
            events = self._load_events()
            retained = [
                event for event in events
                if self._parse_created_at(event.created_at) >= cutoff
            ]
            if len(retained) > self.max_events:
                retained = retained[-self.max_events :]
            if len(retained) == len(events):
                return 0
            self._rewrite(retained)
            return len(events) - len(retained)

    def _load_events(self) -> list[SecurityAuditEvent]:
        if not self.path.exists():
            return []
        events: list[SecurityAuditEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    events.append(SecurityAuditEvent(**payload))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"invalid security audit record at line {line_number}"
                    ) from exc
        return events

    def _rewrite(self, events: Iterable[SecurityAuditEvent]) -> None:
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(
                    json.dumps(
                        {
                            "event_type": event.event_type,
                            "capability": event.capability,
                            "outcome": event.outcome,
                            "actor_id": event.actor_id,
                            "tenant_id": event.tenant_id,
                            "reason": event.reason,
                            "metadata": dict(event.metadata),
                            "created_at": event.created_at,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(self.path)

    @staticmethod
    def _parse_created_at(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
