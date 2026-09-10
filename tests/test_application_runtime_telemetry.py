from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import (
    ApplicationRequest,
    ApplicationRuntime,
    Capability,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    InMemoryMetrics,
    OperationalTelemetry,
)


def _metric(snapshots, name: str, labels: dict[str, str]):
    for snapshot in snapshots:
        if snapshot.name == name and dict(snapshot.labels) == labels:
            return snapshot
    raise AssertionError(f"metric not found: {name} {labels}")


@pytest.mark.asyncio
async def test_runtime_emits_success_telemetry_without_identity_labels() -> None:
    metrics = InMemoryMetrics()
    telemetry = OperationalTelemetry(metrics)

    runtime = ApplicationRuntime(
        {Capability.QUESTION: lambda _: "ok"},
        telemetry=telemetry,
    )

    await runtime.execute(
        ApplicationRequest(
            question="hello",
            session_id="session-secret",
            actor_id="actor-secret",
            tenant_id="tenant-secret",
        )
    )

    snapshots = telemetry.snapshot()
    request = _metric(
        snapshots,
        "application_requests_total",
        {"capability": "question", "status": "started"},
    )
    duration = _metric(
        snapshots,
        "application_duration_ms_total",
        {"capability": "question"},
    )

    assert request.value == 1
    assert duration.value >= 0
    for snapshot in snapshots:
        labels = dict(snapshot.labels)
        assert "actor_id" not in labels
        assert "session_id" not in labels
        assert "tenant_id" not in labels


@pytest.mark.asyncio
async def test_runtime_emits_bounded_error_telemetry_and_reraises() -> None:
    metrics = InMemoryMetrics()
    telemetry = OperationalTelemetry(metrics)

    def failing(_: ApplicationRequest) -> str:
        raise RuntimeError("secret provider details")

    runtime = ApplicationRuntime(
        {Capability.QUESTION: failing},
        telemetry=telemetry,
    )

    with pytest.raises(RuntimeError, match="secret provider details"):
        await runtime.execute(
            ApplicationRequest(
                question="hello",
                actor_id="actor-secret",
                session_id="session-secret",
                tenant_id="tenant-secret",
            )
        )

    snapshots = telemetry.snapshot()
    error = _metric(
        snapshots,
        "application_errors_total",
        {"capability": "question", "error_type": "RuntimeError"},
    )
    duration = _metric(
        snapshots,
        "application_duration_ms_total",
        {"capability": "question"},
    )

    assert error.value == 1
    assert duration.value >= 0
    serialized = repr(snapshots)
    assert "secret provider details" not in serialized
    assert "actor-secret" not in serialized
    assert "session-secret" not in serialized
    assert "tenant-secret" not in serialized
