import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.auth_context import (
    extract_auth_context,
)


class FakeUser:
    def __init__(self, identifier, metadata=None):
        self.identifier = identifier
        self.metadata = metadata or {}


def test_extract_auth_context_keeps_only_non_secret_identity() -> None:
    user = FakeUser(
        "actor-1",
        {
            "tenant_id": "tenant-1",
            "roles": ["reader", "reader", ""],
            "id_token": "SECRET-ID-TOKEN",
            "claims": {"tid": "tenant-1", "sub": "actor-1"},
        },
    )

    context = extract_auth_context(user)

    assert context.actor_id == "actor-1"
    assert context.tenant_id == "tenant-1"
    assert context.roles == frozenset({"reader"})
    assert not hasattr(context, "id_token")
    assert not hasattr(context, "claims")


def test_extract_auth_context_fails_closed_without_authenticated_actor() -> None:
    with pytest.raises(PermissionError):
        extract_auth_context(FakeUser("", {"tenant_id": "tenant-1"}))


def test_extract_auth_context_fails_closed_without_user() -> None:
    with pytest.raises(PermissionError):
        extract_auth_context(None)
