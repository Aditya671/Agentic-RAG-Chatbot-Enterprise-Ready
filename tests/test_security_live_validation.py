from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.auth_context import (
    AuthContext,
    extract_auth_context,
)
from agentic_rag_chatbot_enterprise_ready.frontend.application_surface import ApplicationSurface


class _User:
    def __init__(self, identifier: str, metadata: dict):
        self.identifier = identifier
        self.metadata = metadata


class _Runtime:
    def __init__(self):
        self.calls = []

    async def history(self, conversation_id, actor_id, *, tenant_id=None, limit=100):
        self.calls.append((conversation_id, actor_id, tenant_id, limit))
        return []


@pytest.mark.asyncio
async def test_authenticated_context_accepts_only_identity_boundary_fields():
    user = _User(
        "actor-1",
        {
            "tenant_id": "tenant-a",
            "roles": ["reader", "uploader"],
            "id_token": "legacy-secret",
            "claims": {"sub": "actor-1", "tid": "tenant-a"},
        },
    )

    context = extract_auth_context(user)

    assert context == AuthContext(
        actor_id="actor-1",
        tenant_id="tenant-a",
        roles=frozenset({"reader", "uploader"}),
    )
    assert not hasattr(context, "id_token")
    assert not hasattr(context, "claims")


@pytest.mark.asyncio
async def test_history_surface_propagates_tenant_without_prompt_or_claims():
    runtime = _Runtime()
    surface = ApplicationSurface(runtime)

    history = await surface.history(
        "thread-1",
        actor_id="actor-1",
        tenant_id="tenant-a",
    )

    assert history.conversation_id == "thread-1"
    assert runtime.calls == [("thread-1", "actor-1", "tenant-a", 100)]
