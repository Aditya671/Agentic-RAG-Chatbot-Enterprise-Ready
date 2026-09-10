from datetime import UTC, datetime, timedelta

from agentic_rag_chatbot_enterprise_ready.backend.reliability.security_audit import (
    SecurityAuditEvent,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.security_audit_store import (
    JsonlSecurityAuditSink,
)


def _event(created_at: str, actor_id: str = "actor-1") -> SecurityAuditEvent:
    return SecurityAuditEvent(
        event_type="security.authorization",
        capability="question",
        outcome="allowed",
        actor_id=actor_id,
        tenant_id="tenant-1",
        created_at=created_at,
    )


def test_audit_events_survive_reload(tmp_path):
    path = tmp_path / "security-audit.jsonl"
    sink = JsonlSecurityAuditSink(path, retention_days=90)
    created_at = datetime.now(UTC).isoformat()
    sink.record(_event(created_at))

    reloaded = JsonlSecurityAuditSink(path, retention_days=90)
    events = reloaded.recent()

    assert len(events) == 1
    assert events[0].actor_id == "actor-1"
    assert events[0].tenant_id == "tenant-1"


def test_retention_removes_expired_events(tmp_path):
    path = tmp_path / "security-audit.jsonl"
    sink = JsonlSecurityAuditSink(path, retention_days=7)
    old = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    current = datetime.now(UTC).isoformat()
    sink.record(_event(old, actor_id="old"))
    sink.record(_event(current, actor_id="current"))

    removed = sink.prune()

    assert removed == 1
    assert [event.actor_id for event in sink.recent()] == ["current"]


def test_max_events_retention_keeps_newest_records(tmp_path):
    path = tmp_path / "security-audit.jsonl"
    sink = JsonlSecurityAuditSink(path, retention_days=90, max_events=2)
    now = datetime.now(UTC)
    for index in range(3):
        sink.record(_event((now + timedelta(seconds=index)).isoformat(), actor_id=str(index)))

    sink.prune(now=now + timedelta(seconds=3))

    assert [event.actor_id for event in sink.recent()] == ["2", "1"]


def test_recent_rejects_invalid_limit(tmp_path):
    sink = JsonlSecurityAuditSink(tmp_path / "security-audit.jsonl")

    try:
        sink.recent(0)
    except ValueError as exc:
        assert "positive integer" in str(exc)
    else:
        raise AssertionError("expected invalid limit to fail")
