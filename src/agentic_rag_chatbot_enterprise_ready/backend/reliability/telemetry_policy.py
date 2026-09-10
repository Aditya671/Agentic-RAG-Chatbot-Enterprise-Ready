"""Provider-neutral policy for production telemetry retention and safety."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TelemetryRetentionPolicy:
    """Explicit, bounded retention policy for operational telemetry."""

    trace_retention_days: int = 30
    audit_retention_days: int = 90
    max_trace_records: int = 100_000
    max_audit_records: int = 100_000
    max_detail_length: int = 512

    def __post_init__(self) -> None:
        for name in (
            "trace_retention_days",
            "audit_retention_days",
            "max_trace_records",
            "max_audit_records",
            "max_detail_length",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")

    def bound_detail(self, value: object) -> str:
        """Convert operational detail to a bounded string without exposing raw objects."""
        text = str(value)
        return text[: self.max_detail_length]
