from agentic_rag_chatbot_enterprise_ready.backend.reliability.metrics import InMemoryMetrics
from agentic_rag_chatbot_enterprise_ready.backend.reliability.operational_telemetry import (
    OperationalTelemetry,
)


def test_operational_telemetry_records_bounded_runtime_facts():
    metrics = InMemoryMetrics()
    telemetry = OperationalTelemetry(metrics)

    telemetry.record_request("question", "success")
    telemetry.record_duration_ms("question", 12.5)
    telemetry.record_error("upload", "ValueError")

    snapshots = telemetry.snapshot()
    assert [(item.name, item.metric_type, item.value) for item in snapshots] == [
        ("application_duration_ms_total", "counter", 12.5),
        ("application_errors_total", "counter", 1.0),
        ("application_requests_total", "counter", 1.0),
    ]
    labels = {item.name: dict(item.labels) for item in snapshots}
    assert labels["application_requests_total"] == {
        "capability": "question",
        "status": "success",
    }
    assert labels["application_errors_total"] == {
        "capability": "upload",
        "error_type": "ValueError",
    }


def test_operational_telemetry_does_not_accept_unbounded_identity_fields():
    metrics = InMemoryMetrics(max_label_value_length=16)
    telemetry = OperationalTelemetry(metrics)

    telemetry.record_request("question", "success")
    snapshot = telemetry.snapshot()[0]
    assert "actor_id" not in snapshot.labels
    assert "session_id" not in snapshot.labels
    assert "tenant_id" not in snapshot.labels
