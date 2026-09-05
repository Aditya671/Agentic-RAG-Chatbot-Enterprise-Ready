"""Provider-neutral conversation and message persistence contracts."""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class Conversation:
    conversation_id: str
    actor_id: str
    session_id: str
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    message_id: str
    conversation_id: str
    actor_id: str
    role: str
    content: str
    created_at: str = field(default_factory=utc_now)
    run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationStore(Protocol):
    async def ensure_conversation(self, conversation_id: str, actor_id: str, session_id: str, *, metadata: dict[str, Any] | None = None) -> Conversation: ...
    async def append_message(self, message: ConversationMessage) -> ConversationMessage: ...
    async def list_messages(self, conversation_id: str, actor_id: str, *, limit: int = 100) -> tuple[ConversationMessage, ...]: ...
    async def delete_conversation(self, conversation_id: str, actor_id: str) -> bool: ...


class InMemoryConversationStore:
    """Deterministic conversation store for local execution and harness tests."""

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[ConversationMessage]] = defaultdict(list)

    async def ensure_conversation(self, conversation_id: str, actor_id: str, session_id: str, *, metadata: dict[str, Any] | None = None) -> Conversation:
        if not conversation_id or not actor_id or not session_id:
            raise ValueError("conversation_id, actor_id, and session_id are required")
        existing = self._conversations.get(conversation_id)
        if existing:
            if existing.actor_id != actor_id:
                raise PermissionError("conversation belongs to a different actor")
            if existing.session_id != session_id:
                raise PermissionError("conversation belongs to a different session")
            return existing
        conversation = Conversation(conversation_id, actor_id, session_id, metadata=dict(metadata or {}))
        self._conversations[conversation_id] = conversation
        return conversation

    async def append_message(self, message: ConversationMessage) -> ConversationMessage:
        if not isinstance(message, ConversationMessage):
            raise TypeError("message must be a ConversationMessage")
        conversation = self._conversations.get(message.conversation_id)
        if conversation is None:
            raise KeyError("conversation does not exist")
        if conversation.actor_id != message.actor_id:
            raise PermissionError("message actor does not own conversation")
        if not message.content.strip():
            raise ValueError("message content must be non-empty")
        if message.role not in {"user", "assistant", "system"}:
            raise ValueError("unsupported message role")
        if any(item.message_id == message.message_id for item in self._messages[message.conversation_id]):
            raise ValueError("message already exists")
        self._messages[message.conversation_id].append(message)
        self._conversations[message.conversation_id] = Conversation(
            conversation.conversation_id, conversation.actor_id, conversation.session_id,
            conversation.created_at, utc_now(), conversation.metadata,
        )
        return message

    async def list_messages(self, conversation_id: str, actor_id: str, *, limit: int = 100) -> tuple[ConversationMessage, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            return ()
        if conversation.actor_id != actor_id:
            raise PermissionError("conversation belongs to a different actor")
        return tuple(self._messages[conversation_id][-limit:])

    async def delete_conversation(self, conversation_id: str, actor_id: str) -> bool:
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            return False
        if conversation.actor_id != actor_id:
            raise PermissionError("conversation belongs to a different actor")
        del self._conversations[conversation_id]
        self._messages.pop(conversation_id, None)
        return True


class ConversationService:
    """Application-facing facade that keeps persistence provider-neutral."""

    def __init__(self, store: ConversationStore) -> None:
        self.store = store

    async def ensure(self, conversation_id: str, actor_id: str, session_id: str) -> Conversation:
        return await self.store.ensure_conversation(conversation_id, actor_id, session_id)

    async def record_turn(self, conversation_id: str, actor_id: str, *, question: str, answer: str, run_id: str | None = None) -> tuple[ConversationMessage, ConversationMessage]:
        if not question.strip() or not answer.strip():
            raise ValueError("question and answer must be non-empty")
        user_message = ConversationMessage(str(uuid.uuid4()), conversation_id, actor_id, "user", question.strip(), run_id=run_id)
        assistant_message = ConversationMessage(str(uuid.uuid4()), conversation_id, actor_id, "assistant", answer.strip(), run_id=run_id)
        await self.store.append_message(user_message)
        await self.store.append_message(assistant_message)
        return user_message, assistant_message

    async def history(self, conversation_id: str, actor_id: str, *, limit: int = 100) -> tuple[ConversationMessage, ...]:
        return await self.store.list_messages(conversation_id, actor_id, limit=limit)
