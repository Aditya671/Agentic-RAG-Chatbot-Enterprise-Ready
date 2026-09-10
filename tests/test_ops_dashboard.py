from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    Alert,
    AlertSeverity,
    FailureTriage,
    HealthSnapshot,
    OperationalDashboard,
    OperationalDashboardBuilder,
    TriagePriority,
    export_dashboard,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.metrics import MetricSnapshot


def test_dashboard_build_is_read_only_and_bounded():
    health = HealthSnapshot(10, 8, 2, 0.2, 0.7)
    metrics = (MetricSnapshot("requests", "counter", 10.0, {"capability": "question"}),)
    alerts = (Alert("alert-1", AlertSeverity.WARNING, "error_rate", 0.2, "error rate elevated"),)
    snapshot = OperationalDashboardBuilder().build(health, metrics=metrics, alerts=alerts)

    assert isinstance(snapshot, OperationalDashboard)
    assert snapshot.health == health
    assert snapshot.metrics == metrics
    assert snapshot.alerts == alerts


def test_dashboard_export_contains_no_execution_identity_fields():
    snapshot = OperationalDashboardBuilder().build(
        HealthSnapshot(1, 0, 1, 1.0, 0.0),
        metrics=(MetricSnapshot("errors", "counter", 1.0, {"capability": "question", "error_type": "RuntimeError"}),),
    )
    exported = export_dashboard(snapshot)
    text = repr(exported)
    assert "actor_id" not in text
    assert "session_id" not in text
    assert "tenant_id" not in text
    assert "request_id" not in text
    assert "prompt" not in text


def test_dashboard_builder_rejects_unbounded_item_sets():
    health = HealthSnapshot(1, 1, 0, 0.0, 1.0)
    metrics = tuple(MetricSnapshot(f"m-{i}", "counter", 1.0) for i in range(101))
    try:
        OperationalDashboardBuilder().build(health, metrics=metrics)
    except ValueError as exc:
        assert "item limit" in str(exc)
    else:
        raise AssertionError("expected dashboard item limit")
