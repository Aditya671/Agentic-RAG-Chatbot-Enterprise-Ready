import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.security import (
    SecurityPolicy,
    SecurityPrincipal,
    principal_from_request,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.security_audit import (
    InMemorySecurityAuditSink,
)


def test_principal_requires_authenticated_identity() -> None:
    with pytest.raises(PermissionError):
        principal_from_request(None, "session-1")
    with pytest.raises(PermissionError):
        principal_from_request("actor-1", None)


def test_capability_policy_enforces_required_role() -> None:
    policy = SecurityPolicy(required_roles={"upload": frozenset({"uploader"})})
    principal = SecurityPrincipal("actor-1", "session-1", roles=frozenset({"reader"}))
    with pytest.raises(PermissionError):
        policy.authorize(principal, "upload")


def test_capability_policy_allows_matching_role() -> None:
    policy = SecurityPolicy(required_roles={"upload": frozenset({"uploader"})})
    principal = SecurityPrincipal("actor-1", "session-1", roles=frozenset({"uploader"}))
    policy.authorize(principal, "upload")


def test_capability_policy_audits_allowed_and_denied_decisions() -> None:
    sink = InMemorySecurityAuditSink()
    policy = SecurityPolicy(
        required_roles={"upload": frozenset({"uploader"})},
        audit_sink=sink,
    )
    allowed = SecurityPrincipal(
        "actor-1", "session-1", tenant_id="tenant-1", roles=frozenset({"uploader"})
    )
    denied = SecurityPrincipal(
        "actor-2", "session-2", tenant_id="tenant-2", roles=frozenset({"reader"})
    )

    policy.authorize(allowed, "upload")
    with pytest.raises(PermissionError):
        policy.authorize(denied, "upload")

    assert [(event.outcome, event.reason) for event in sink.events] == [
        ("allowed", None),
        ("denied", "role_required"),
    ]
    assert sink.events[1].actor_id == "actor-2"
    assert sink.events[1].tenant_id == "tenant-2"


def test_upload_policy_rejects_unsafe_extension_and_size() -> None:
    policy = SecurityPolicy(max_upload_size_bytes=4)
    with pytest.raises(ValueError):
        policy.validate_uploads([{"name": "script.py", "content": b"x"}])
    with pytest.raises(ValueError):
        policy.validate_uploads([{"name": "ok.txt", "content": b"12345"}])


def test_upload_policy_rejects_path_components() -> None:
    policy = SecurityPolicy()
    for name in ("../ok.txt", "..\\ok.txt", "folder/ok.txt", "folder\\ok.txt"):
        with pytest.raises(ValueError):
            policy.validate_uploads([{"name": name, "content": b"ok"}])


def test_upload_policy_requires_bytes() -> None:
    with pytest.raises(TypeError):
        SecurityPolicy().validate_uploads([{"name": "ok.txt", "content": "text"}])
