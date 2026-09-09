import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.security_audit import (
    InMemorySecurityAuditSink,
    SecurityAuditEvent,
)


def test_security_audit_event_contains_only_bounded_security_metadata() -> None:
    event = SecurityAuditEvent(
        event_type="security.authorization",
        capability="upload",
        outcome="denied",
        actor_id="actor-1",
        tenant_id="tenant-1",
        reason="role_required",
        metadata={"role": "uploader"},
    )

    assert event.capability == "upload"
    assert event.outcome == "denied"
    assert event.metadata == {"role": "uploader"}
    assert not hasattr(event, "prompt")
    assert not hasattr(event, "content")
    assert not hasattr(event, "token")
    assert not hasattr(event, "claims")


def test_security_audit_event_rejects_missing_identity() -> None:
    with pytest.raises(ValueError):
        SecurityAuditEvent(
            event_type="security.authorization",
            capability="question",
            outcome="denied",
            actor_id="",
        )


def test_in_memory_security_audit_sink_records_events() -> None:
    sink = InMemorySecurityAuditSink()
    event = SecurityAuditEvent(
        event_type="security.authorization",
        capability="question",
        outcome="allowed",
        actor_id="actor-1",
    )

    sink.record(event)

    assert sink.events == [event]
