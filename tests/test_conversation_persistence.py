from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import (
    ApplicationRequest,
    ApplicationRuntime,
    Capability,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    ChainlitConversationStore,
    ConversationMessage,
    ConversationService,
    InMemoryConversationStore,
)


@pytest.mark.asyncio
async def test_runtime_persists_successful_question_turn_and_history() -> None:
    store = InMemoryConversationStore()

    async def answer(_: ApplicationRequest):
        return "Grounded answer."

    runtime = ApplicationRuntime(
        {Capability.QUESTION: answer},
        conversation_store=store,
    )
    execution = await runtime.execute(
        ApplicationRequest(
            question="  What   is the policy? ",
            session_id="session-1",
            actor_id="actor-1",
            conversation_id="conversation-1",
        )
    )

    history = await runtime.history("conversation-1", "actor-1")
    assert execution.result.conversation_id == "conversation-1"
    assert execution.result.metadata["conversation_id"] == "conversation-1"
    assert [message.role for message in history] == ["user", "assistant"]
    assert history[0].content == "What is the policy?"
    assert history[1].content == "Grounded answer."
    assert history[0].run_id == execution.trace.run_id
    assert history[1].run_id == execution.trace.run_id
    assert any(event.name == "conversation.persisted" for event in execution.trace.events)


@pytest.mark.asyncio
async def test_runtime_requires_identity_when_persistence_is_enabled() -> None:
    runtime = ApplicationRuntime(
        {Capability.QUESTION: lambda _: "answer"},
        conversation_store=InMemoryConversationStore(),
    )

    with pytest.raises(ValueError, match="conversation_id, actor_id, and session_id"):
        await runtime.execute(ApplicationRequest(question="hello"))


@pytest.mark.asyncio
async def test_failed_question_is_not_persisted_as_a_turn() -> None:
    store = InMemoryConversationStore()

    async def failing(_: ApplicationRequest):
        raise RuntimeError("retrieval unavailable")

    runtime = ApplicationRuntime({Capability.QUESTION: failing}, conversation_store=store)

    with pytest.raises(RuntimeError, match="retrieval unavailable"):
        await runtime.execute(
            ApplicationRequest(
                question="hello",
                session_id="session-1",
                actor_id="actor-1",
                conversation_id="conversation-1",
            )
        )

    assert await runtime.history("conversation-1", "actor-1") == ()


@pytest.mark.asyncio
async def test_conversation_isolation_blocks_other_actor_and_session() -> None:
    store = InMemoryConversationStore()
    await store.ensure_conversation("conversation-1", "actor-1", "session-1")

    with pytest.raises(PermissionError, match="different actor"):
        await store.ensure_conversation("conversation-1", "actor-2", "session-1")
    with pytest.raises(PermissionError, match="different session"):
        await store.ensure_conversation("conversation-1", "actor-1", "session-2")
    with pytest.raises(PermissionError, match="different actor"):
        await store.list_messages("conversation-1", "actor-2")


@pytest.mark.asyncio
async def test_duplicate_message_id_is_rejected_and_delete_is_scoped() -> None:
    store = InMemoryConversationStore()
    await store.ensure_conversation("conversation-1", "actor-1", "session-1")
    message = ConversationMessage("message-1", "conversation-1", "actor-1", "user", "hello")
    await store.append_message(message)

    with pytest.raises(ValueError, match="already exists"):
        await store.append_message(message)
    with pytest.raises(PermissionError, match="different actor"):
        await store.delete_conversation("conversation-1", "actor-2")
    assert await store.delete_conversation("conversation-1", "actor-1") is True
    assert await store.list_messages("conversation-1", "actor-1") == ()


class FakeDataLayer:
    def __init__(self):
        self.threads = {}

    async def get_thread(self, thread_id):
        return self.threads.get(thread_id)

    async def update_thread(self, thread_id, name=None, user_id=None, metadata=None, tags=None):
        self.threads.setdefault(thread_id, {
            "id": thread_id,
            "type": "thread",
            "userId": user_id,
            "metadata": metadata or {},
            "steps": [],
        })
        self.threads[thread_id]["userId"] = user_id or self.threads[thread_id].get("userId")
        self.threads[thread_id]["metadata"] = metadata or self.threads[thread_id].get("metadata", {})

    async def create_step(self, step):
        self.threads[step["threadId"]]["steps"].append(step)

    async def delete_thread(self, thread_id):
        self.threads.pop(thread_id, None)


@pytest.mark.asyncio
async def test_chainlit_adapter_translates_stable_contract() -> None:
    layer = FakeDataLayer()
    store = ChainlitConversationStore(layer)
    await store.ensure_conversation("conversation-1", "actor-1", "session-1")
    message = ConversationMessage("message-1", "conversation-1", "actor-1", "assistant", "answer", metadata={"run_id": "run-1"})
    await store.append_message(message)

    history = await store.list_messages("conversation-1", "actor-1")
    assert history == (message,)
    assert layer.threads["conversation-1"]["steps"][0]["output"] == "answer"
