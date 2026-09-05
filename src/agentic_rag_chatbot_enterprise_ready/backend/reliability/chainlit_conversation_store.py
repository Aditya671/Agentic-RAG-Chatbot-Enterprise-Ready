"""Adapter from the provider-neutral conversation contract to Chainlit data layers."""
from __future__ import annotations

from typing import Any

from .conversation import Conversation, ConversationMessage


class ChainlitConversationStore:
    """Persist conversations through an injected Chainlit-compatible data layer.

    Cosmos DB and MongoDB implementations already own their provider-specific
    connection, partition/index, and SDK behavior. This adapter only translates
    the stable application contract into Chainlit thread/step records.
    """

    def __init__(self, data_layer: Any) -> None:
        if data_layer is None:
            raise ValueError("data_layer is required")
        self.data_layer = data_layer

    async def ensure_conversation(self, conversation_id: str, actor_id: str, session_id: str, *, metadata: dict[str, Any] | None = None) -> Conversation:
        if not conversation_id or not actor_id or not session_id:
            raise ValueError("conversation_id, actor_id, and session_id are required")
        existing = await self.data_layer.get_thread(conversation_id)
        if existing is not None:
            stored_actor = existing.get("userId")
            if stored_actor is not None and str(stored_actor) != actor_id:
                raise PermissionError("conversation belongs to a different actor")
            stored_metadata = dict(existing.get("metadata") or {})
            stored_session = str(stored_metadata.get("session_id") or session_id)
            if stored_session != session_id:
                raise PermissionError("conversation belongs to a different session")
            return Conversation(
                conversation_id,
                actor_id,
                stored_session,
                str(existing.get("createdAt") or ""),
                str(existing.get("updatedAt") or existing.get("createdAt") or ""),
                stored_metadata,
            )
        await self.data_layer.update_thread(
            conversation_id,
            user_id=actor_id,
            metadata={**(metadata or {}), "session_id": session_id},
        )
        return Conversation(conversation_id, actor_id, session_id, metadata=dict(metadata or {}))

    async def append_message(self, message: ConversationMessage) -> ConversationMessage:
        if not isinstance(message, ConversationMessage):
            raise TypeError("message must be a ConversationMessage")
        thread = await self.data_layer.get_thread(message.conversation_id)
        if thread is None:
            raise KeyError("conversation does not exist")
        stored_actor = thread.get("userId")
        if stored_actor is not None and str(stored_actor) != message.actor_id:
            raise PermissionError("message actor does not own conversation")
        await self.data_layer.create_step({
            "id": message.message_id,
            "threadId": message.conversation_id,
            "type": f"{message.role}_message",
            "name": message.role,
            "output": message.content,
            "createdAt": message.created_at,
            "userId": message.actor_id,
            "metadata": {**message.metadata, "run_id": message.run_id},
        })
        return message

    async def list_messages(self, conversation_id: str, actor_id: str, *, limit: int = 100) -> tuple[ConversationMessage, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        thread = await self.data_layer.get_thread(conversation_id)
        if not thread:
            return ()
        stored_actor = thread.get("userId")
        if stored_actor is not None and str(stored_actor) != actor_id:
            raise PermissionError("conversation belongs to a different actor")
        messages = []
        for step in thread.get("steps", [])[-limit:]:
            role = str(step.get("type", "")).removesuffix("_message")
            if role not in {"user", "assistant", "system"}:
                continue
            messages.append(ConversationMessage(
                str(step.get("id")), conversation_id, actor_id, role,
                str(step.get("output") or step.get("input") or ""),
                str(step.get("createdAt") or ""),
                (step.get("metadata") or {}).get("run_id"),
                dict(step.get("metadata") or {}),
            ))
        return tuple(messages)

    async def delete_conversation(self, conversation_id: str, actor_id: str) -> bool:
        thread = await self.data_layer.get_thread(conversation_id)
        if not thread:
            return False
        stored_actor = thread.get("userId")
        if stored_actor is not None and str(stored_actor) != actor_id:
            raise PermissionError("conversation belongs to a different actor")
        await self.data_layer.delete_thread(conversation_id)
        return True
