from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.auth_context import (
    extract_auth_context,
)


class _User:
    def __init__(self, identifier: str, metadata: dict):
        self.identifier = identifier
        self.metadata = metadata


def test_auth_context_ignores_legacy_secret_and_claim_metadata() -> None:
    user = _User(
        "actor-1",
        {
            "tenant_id": "tenant-1",
            "roles": ["group-reader"],
            "id_token": "secret-id-token",
            "claims": {"tid": "tenant-1", "sub": "actor-1"},
            "tenant": "tenant-1",
            "groups": [{"id": "group-reader"}],
        },
    )

    context = extract_auth_context(user)

    assert context.actor_id == "actor-1"
    assert context.tenant_id == "tenant-1"
    assert context.roles == frozenset({"group-reader"})
    assert not hasattr(context, "id_token")
    assert not hasattr(context, "claims")


def test_auth_context_requires_authenticated_identity() -> None:
    with pytest.raises(PermissionError):
        extract_auth_context(None)


def test_auth_context_does_not_infer_identity_from_claims() -> None:
    user = _User(
        "",
        {
            "claims": {"sub": "actor-from-claim", "tid": "tenant-from-claim"},
            "roles": ["reader"],
        },
    )

    with pytest.raises(PermissionError):
        extract_auth_context(user)
