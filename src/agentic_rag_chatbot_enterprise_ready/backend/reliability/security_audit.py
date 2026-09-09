"""Provider-neutral security audit facts with bounded, non-content fields."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SecurityAuditEvent:
    """A security decision record that deliberately excludes payload content."""

    event_type: str
    capability: str
    outcome: str
    actor_id: str
    tenant_id: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("event_type must be non-empty")
        if not self.capability.strip():
            raise ValueError("capability must be non-empty")
        if not self.outcome.strip():
            raise ValueError("outcome must be non-empty")
        if not self.actor_id.strip():
            raise ValueError("actor_id must be non-empty")
        if self.tenant_id is not None and not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty when provided")


class InMemorySecurityAuditSink:
    """Deterministic sink for tests and local inspection."""

    def __init__(self) -> None:
        self.events: list[SecurityAuditEvent] = []

    def record(self, event: SecurityAuditEvent) -> None:
        if not isinstance(event, SecurityAuditEvent):
            raise TypeError("event must be a SecurityAuditEvent")
        self.events.append(event)
