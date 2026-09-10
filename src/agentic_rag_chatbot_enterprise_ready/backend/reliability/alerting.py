"""Provider-neutral production alert evaluation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .retrospective import HealthSnapshot


_MAX_TEXT_LENGTH = 128


class AlertSeverity(StrEnum):
    """Stable severity values for operational alert routing."""

    WARNING = "warning"
    CRITICAL = "critical"


class AlertRule(StrEnum):
    """Built-in deterministic alert rule identifiers."""

    ERROR_RATE = "error_rate"
    EVIDENCE_COVERAGE = "evidence_coverage"


@dataclass(frozen=True, slots=True)
class Alert:
    """Bounded operational alert produced from an immutable health snapshot."""

    rule: AlertRule
    severity: AlertSeverity
    value: float
    threshold: float
    message: str


@dataclass(frozen=True, slots=True)
class AlertPolicy:
    """Thresholds for deterministic alert evaluation."""

    error_rate_warning: float = 0.10
    error_rate_critical: float = 0.25
    evidence_coverage_warning: float = 0.90

    def __post_init__(self) -> None:
        for value, name in (
            (self.error_rate_warning, "error_rate_warning"),
            (self.error_rate_critical, "error_rate_critical"),
            (self.evidence_coverage_warning, "evidence_coverage_warning"),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"{name} must be numeric")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.error_rate_warning > self.error_rate_critical:
            raise ValueError("error_rate_warning must not exceed error_rate_critical")


class AlertEngine:
    """Evaluate bounded alerts from existing monitoring facts only."""

    def __init__(self, policy: AlertPolicy | None = None) -> None:
        self.policy = policy or AlertPolicy()

    def evaluate(self, snapshot: HealthSnapshot) -> tuple[Alert, ...]:
        if not isinstance(snapshot, HealthSnapshot):
            raise TypeError("snapshot must be a HealthSnapshot")

        alerts: list[Alert] = []
        error_rate = float(snapshot.error_rate)
        if error_rate >= self.policy.error_rate_critical:
            alerts.append(
                self._alert(
                    AlertRule.ERROR_RATE,
                    AlertSeverity.CRITICAL,
                    error_rate,
                    self.policy.error_rate_critical,
                    "error rate exceeded critical threshold",
                )
            )
        elif error_rate >= self.policy.error_rate_warning:
            alerts.append(
                self._alert(
                    AlertRule.ERROR_RATE,
                    AlertSeverity.WARNING,
                    error_rate,
                    self.policy.error_rate_warning,
                    "error rate exceeded warning threshold",
                )
            )

        evidence_coverage = float(snapshot.evidence_coverage)
        if evidence_coverage < self.policy.evidence_coverage_warning:
            alerts.append(
                self._alert(
                    AlertRule.EVIDENCE_COVERAGE,
                    AlertSeverity.WARNING,
                    evidence_coverage,
                    self.policy.evidence_coverage_warning,
                    "evidence coverage fell below warning threshold",
                )
            )
        return tuple(alerts)

    @staticmethod
    def _alert(
        rule: AlertRule,
        severity: AlertSeverity,
        value: float,
        threshold: float,
        message: str,
    ) -> Alert:
        return Alert(
            rule=rule,
            severity=severity,
            value=value,
            threshold=threshold,
            message=message[:_MAX_TEXT_LENGTH],
        )
