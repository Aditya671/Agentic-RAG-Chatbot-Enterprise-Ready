import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.health import (
    HealthCheck,
    HealthService,
    HealthStatus,
)


def test_liveness_is_healthy_without_dependency_calls():
    service = HealthService(checks=[lambda: (_ for _ in ()).throw(AssertionError("must not run"))])

    report = service.liveness()

    assert report.status is HealthStatus.HEALTHY
    assert report.ready is True
    assert report.to_dict()["metadata"] == {"probe": "liveness"}


def test_readiness_aggregates_healthy_checks():
    service = HealthService(
        checks=[
            lambda: HealthCheck("database", HealthStatus.HEALTHY),
            lambda: HealthCheck("search", HealthStatus.HEALTHY),
        ],
        version="1.0.0",
    )

    report = service.readiness()

    assert report.status is HealthStatus.HEALTHY
    assert report.ready is True
    assert [item.name for item in report.checks] == ["database", "search"]
    assert report.version == "1.0.0"


def test_readiness_is_degraded_when_any_dependency_is_degraded():
    service = HealthService(
        checks=[
            lambda: HealthCheck("database", HealthStatus.HEALTHY),
            lambda: HealthCheck("search", HealthStatus.DEGRADED, "temporarily slow"),
        ]
    )

    report = service.readiness()

    assert report.status is HealthStatus.DEGRADED
    assert report.ready is False


def test_readiness_fails_closed_on_dependency_exception_without_raw_error():
    def broken_check():
        raise RuntimeError("database password=super-secret")

    service = HealthService(checks=[broken_check])

    report = service.readiness()

    assert report.status is HealthStatus.UNHEALTHY
    assert report.ready is False
    assert report.checks[0].detail == "check failed: RuntimeError"
    assert "super-secret" not in report.checks[0].detail


def test_health_check_rejects_unbounded_detail():
    with pytest.raises(ValueError, match="at most 500"):
        HealthCheck("dependency", HealthStatus.UNHEALTHY, "x" * 501)


def test_non_health_check_result_is_rejected():
    service = HealthService(checks=[lambda: "healthy"])

    with pytest.raises(TypeError, match="HealthCheck"):
        service.readiness()
