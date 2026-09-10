import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.telemetry_policy import (
    TelemetryRetentionPolicy,
)


def test_defaults_are_explicit_and_positive():
    policy = TelemetryRetentionPolicy()
    assert policy.trace_retention_days == 30
    assert policy.audit_retention_days == 90
    assert policy.max_trace_records == 100_000
    assert policy.max_audit_records == 100_000
    assert policy.max_detail_length == 512


def test_policy_rejects_non_positive_limits():
    for field in (
        "trace_retention_days",
        "audit_retention_days",
        "max_trace_records",
        "max_audit_records",
        "max_detail_length",
    ):
        with pytest.raises(ValueError):
            TelemetryRetentionPolicy(**{field: 0})


def test_policy_rejects_boolean_limits():
    with pytest.raises(ValueError):
        TelemetryRetentionPolicy(max_trace_records=True)


def test_bound_detail_is_deterministic_and_limited():
    policy = TelemetryRetentionPolicy(max_detail_length=5)
    assert policy.bound_detail("123456789") == "12345"
    assert policy.bound_detail(123456789) == "12345"
