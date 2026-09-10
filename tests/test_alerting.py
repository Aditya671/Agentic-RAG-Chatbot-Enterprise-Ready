from agentic_rag_chatbot_enterprise_ready.backend.reliability.alerting import (
    AlertEngine,
    AlertPolicy,
    AlertRule,
    AlertSeverity,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.retrospective import HealthSnapshot


def test_error_rate_alerts_are_deterministic_and_ordered_by_rule():
    snapshot = HealthSnapshot(
        total_runs=100,
        successful_runs=70,
        failed_runs=30,
        error_rate=0.30,
        evidence_coverage=0.80,
    )

    alerts = AlertEngine().evaluate(snapshot)

    assert [alert.rule for alert in alerts] == [
        AlertRule.ERROR_RATE,
        AlertRule.EVIDENCE_COVERAGE,
    ]
    assert alerts[0].severity is AlertSeverity.CRITICAL
    assert alerts[0].threshold == 0.25
    assert alerts[1].severity is AlertSeverity.WARNING


def test_warning_thresholds_do_not_emit_critical_alerts():
    snapshot = HealthSnapshot(100, 90, 10, 0.10, 0.89)

    alerts = AlertEngine().evaluate(snapshot)

    assert [alert.severity for alert in alerts] == [AlertSeverity.WARNING]
    assert alerts[0].rule is AlertRule.EVIDENCE_COVERAGE


def test_healthy_snapshot_has_no_alerts():
    snapshot = HealthSnapshot(100, 98, 2, 0.02, 0.98)

    assert AlertEngine().evaluate(snapshot) == ()


def test_policy_rejects_invalid_ranges_and_inverted_error_thresholds():
    with __import__("pytest").raises(ValueError):
        AlertPolicy(error_rate_warning=0.3, error_rate_critical=0.2)
    with __import__("pytest").raises(ValueError):
        AlertPolicy(evidence_coverage_warning=1.1)
