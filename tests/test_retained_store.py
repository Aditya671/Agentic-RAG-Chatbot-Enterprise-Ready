from datetime import UTC, datetime, timedelta

from agentic_rag_chatbot_enterprise_ready.backend.reliability.retained_store import (
    RetainedAuditSink,
    RetainedTraceStore,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.security_audit import (
    InMemorySecurityAuditSink,
    SecurityAuditEvent,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.telemetry_policy import (
    TelemetryRetentionPolicy,
)


class FakeTraceStore:
    def __init__(self):
        self.saved = []

    def save(self, trace):
        self.saved.append(trace)

    def get(self, run_id):
        return next((item for item in self.saved if item.run_id == run_id), None)

    def recent(self, limit=20):
        return list(reversed(self.saved[-limit:]))

    def __iter__(self):
        return iter(self.saved)


def test_retained_trace_store_delegates_without_creating_parallel_storage():
    store = FakeTraceStore()
    wrapped = RetainedTraceStore(store, policy=TelemetryRetentionPolicy())
    assert wrapped.store is store
    assert list(wrapped) == []


def test_retained_audit_sink_filters_by_policy_retention_window():
    inner = InMemorySecurityAuditSink()
    policy = TelemetryRetentionPolicy(audit_retention_days=7, max_audit_records=10)
    sink = RetainedAuditSink(inner, policy=policy)
    now = datetime(2026, 9, 10, tzinfo=UTC)

    inner.record(SecurityAuditEvent("security.authorization", "question", "allowed", "a", created_at=(now - timedelta(days=1)).isoformat()))
    inner.record(SecurityAuditEvent("security.authorization", "question", "allowed", "b", created_at=(now - timedelta(days=8)).isoformat()))

    assert [event.actor_id for event in sink.retained(now=now)] == ["a"]


def test_retained_audit_sink_respects_maximum_records():
    inner = InMemorySecurityAuditSink()
    policy = TelemetryRetentionPolicy(audit_retention_days=30, max_audit_records=1)
    sink = RetainedAuditSink(inner, policy=policy)
    now = datetime(2026, 9, 10, tzinfo=UTC)

    for actor in ("a", "b"):
        inner.record(SecurityAuditEvent("security.authorization", "question", "allowed", actor, created_at=now.isoformat()))

    assert [event.actor_id for event in sink.retained(now=now)] == ["b"]
