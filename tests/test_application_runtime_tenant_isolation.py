import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import (
    ApplicationRequest,
    ApplicationRuntime,
    Capability,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.conversation import (
    InMemoryConversationStore,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.security import SecurityPolicy


@pytest.mark.asyncio
async def test_persisted_question_rejects_cross_tenant_conversation_before_handler() -> None:
    store = InMemoryConversationStore()
    await store.ensure_conversation(
        "conversation-1",
        "actor-1",
        "session-1",
        tenant_id="tenant-a",
    )

    called = False

    async def handler(_request: ApplicationRequest) -> str:
        nonlocal called
        called = True
        return "should not execute"

    runtime = ApplicationRuntime(
        {Capability.QUESTION: handler},
        conversation_store=store,
        security_policy=SecurityPolicy(),
    )

    with pytest.raises(PermissionError, match="different tenant"):
        await runtime.execute(
            ApplicationRequest(
                question="hello",
                capability=Capability.QUESTION,
                actor_id="actor-1",
                session_id="session-1",
                conversation_id="conversation-1",
                tenant_id="tenant-b",
            )
        )

    assert called is False
