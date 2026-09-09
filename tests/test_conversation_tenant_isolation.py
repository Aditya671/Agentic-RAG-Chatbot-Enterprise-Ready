import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.conversation import (
    InMemoryConversationStore,
)


@pytest.mark.asyncio
async def test_conversation_tenant_isolation() -> None:
    store = InMemoryConversationStore()

    await store.ensure_conversation(
        "conversation-1",
        "actor-1",
        "session-1",
        tenant_id="tenant-a",
    )

    with pytest.raises(PermissionError, match="different tenant"):
        await store.ensure_conversation(
            "conversation-1",
            "actor-1",
            "session-1",
            tenant_id="tenant-b",
        )

    with pytest.raises(PermissionError, match="different tenant"):
        await store.list_messages(
            "conversation-1",
            "actor-1",
            tenant_id="tenant-b",
        )

    with pytest.raises(PermissionError, match="different tenant"):
        await store.delete_conversation(
            "conversation-1",
            "actor-1",
            tenant_id="tenant-b",
        )


@pytest.mark.asyncio
async def test_legacy_conversation_without_tenant_is_accessible_without_tenant_filter() -> None:
    store = InMemoryConversationStore()
    await store.ensure_conversation("conversation-1", "actor-1", "session-1")

    history = await store.list_messages("conversation-1", "actor-1")
    assert history == ()
