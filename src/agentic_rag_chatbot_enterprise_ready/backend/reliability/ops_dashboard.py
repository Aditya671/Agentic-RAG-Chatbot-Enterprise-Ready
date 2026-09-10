"""Provider-neutral operational dashboard/export contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .alerting import Alert
from .metrics import MetricSnapshot
from .retrospective import HealthSnapshot
from .triage import FailureTriage


_MAX_ITEMS = 100
_MAX_TEXT = 256


@dataclass(frozen=True, slots=True)
class OperationalDashboard:
    """Bounded read-only operational view safe for export."""

    health: HealthSnapshot
    metrics: tuple[MetricSnapshot, ...] = ()
    alerts: tuple[Alert, ...] = ()
    triage: FailureTriage | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class OperationalDashboardBuilder:
    """Build deterministic dashboard snapshots without trace/payload exposure."""

    def build(
        self,
        health: HealthSnapshot,
        *,
        metrics: Iterable[MetricSnapshot] = (),
        alerts: Iterable[Alert] = (),
        triage: FailureTriage | None = None,
    ) -> OperationalDashboard:
        if not isinstance(health, HealthSnapshot):
            raise TypeError("health must be a HealthSnapshot")
        normalized_metrics = tuple(metrics)
        normalized_alerts = tuple(alerts)
        if len(normalized_metrics) > _MAX_ITEMS:
            raise ValueError("metrics exceed dashboard item limit")
        if len(normalized_alerts) > _MAX_ITEMS:
            raise ValueError("alerts exceed dashboard item limit")
        if triage is not None and not isinstance(triage, FailureTriage):
            raise TypeError("triage must be a FailureTriage or None")
        return OperationalDashboard(
            health=health,
            metrics=normalized_metrics,
            alerts=normalized_alerts,
            triage=triage,
        )


def export_dashboard(snapshot: OperationalDashboard) -> dict:
    """Return a bounded JSON-compatible dashboard payload."""
    if not isinstance(snapshot, OperationalDashboard):
        raise TypeError("snapshot must be an OperationalDashboard")
    payload = snapshot.to_dict()
    return _sanitize_payload(payload)


def _sanitize_payload(value):
    if isinstance(value, dict):
        return {str(key): _sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_ITEMS:
            raise ValueError("dashboard collection exceeds item limit")
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, str):
        return value[:_MAX_TEXT]
    return value
