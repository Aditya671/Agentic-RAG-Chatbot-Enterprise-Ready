"""Provider-neutral operational telemetry facade."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .metrics import InMemoryMetrics


@dataclass(slots=True)
class OperationalTelemetry:
    """Record bounded runtime counters without payload or identity labels."""

    metrics: InMemoryMetrics

    def record_request(self, capability: str, status: str) -> None:
        self.metrics.increment(
            "application_requests_total",
            labels={"capability": capability, "status": status},
        )

    def record_duration_ms(self, capability: str, duration_ms: float) -> None:
        self.metrics.increment(
            "application_duration_ms_total",
            duration_ms,
            labels={"capability": capability},
        )

    def record_error(self, capability: str, error_type: str) -> None:
        self.metrics.increment(
            "application_errors_total",
            labels={"capability": capability, "error_type": error_type},
        )

    def snapshot(self):
        """Return deterministic metric snapshots for inspection/export."""
        return self.metrics.snapshot()


def build_operational_telemetry(
    metrics: InMemoryMetrics | None = None,
) -> OperationalTelemetry:
    return OperationalTelemetry(metrics=metrics or InMemoryMetrics())
