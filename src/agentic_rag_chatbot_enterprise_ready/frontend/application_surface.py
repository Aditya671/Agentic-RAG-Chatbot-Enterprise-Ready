"""Provider-neutral UI/API surface over the canonical application runtime."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from ..backend.application_runtime import ApplicationExecution, ApplicationRequest, ApplicationRuntime, Capability
from ..backend.reliability import ConversationMessage, Evidence


@dataclass(frozen=True, slots=True)
class EvidenceView:
    """Client-safe evidence projection."""

    source: str
    locator: str | None
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ApplicationView:
    """Stable presentation payload for Chainlit or a future HTTP API."""

    response_text: str
    capability: str
    run_id: str
    conversation_id: str | None
    evidence: tuple[EvidenceView, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class HistoryView:
    """Client-safe conversation history projection."""

    messages: tuple[dict[str, Any], ...]
    conversation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"conversation_id": self.conversation_id, "messages": list(self.messages)}


def _evidence_view(item: Evidence) -> EvidenceView:
    return EvidenceView(source=item.source, locator=item.locator, metadata=dict(item.metadata))


def present_execution(execution: ApplicationExecution) -> ApplicationView:
    """Project a canonical execution into a serializable client response."""
    result = execution.result
    return ApplicationView(
        response_text=result.response_text,
        capability=result.capability.value,
        run_id=result.run_id,
        conversation_id=result.conversation_id,
        evidence=tuple(_evidence_view(item) for item in result.evidence),
        metadata=dict(result.metadata),
    )


def present_history(messages: Sequence[ConversationMessage], conversation_id: str) -> HistoryView:
    """Project persisted messages without exposing provider-specific objects."""
    return HistoryView(
        conversation_id=conversation_id,
        messages=tuple(
            {
                "message_id": item.message_id,
                "role": item.role,
                "content": item.content,
                "created_at": item.created_at,
                "run_id": item.run_id,
                "metadata": dict(item.metadata),
            }
            for item in messages
        ),
    )


class ApplicationSurface:
    """Thin UI/API facade that delegates all execution to ApplicationRuntime."""

    def __init__(self, runtime: ApplicationRuntime) -> None:
        self._runtime = runtime

    async def question(self, question: str, *, session_id: str, actor_id: str, conversation_id: str, payload: Mapping[str, Any] | None = None) -> ApplicationView:
        execution = await self._runtime.execute(
            ApplicationRequest(
                question=question,
                capability=Capability.QUESTION,
                payload=dict(payload or {}),
                session_id=session_id,
                actor_id=actor_id,
                conversation_id=conversation_id,
            )
        )
        return present_execution(execution)

    async def upload(self, uploaded_files: Sequence[Mapping[str, Any]], *, session_id: str, actor_id: str, conversation_id: str | None = None) -> ApplicationView:
        execution = await self._runtime.execute(
            ApplicationRequest(
                capability=Capability.UPLOAD,
                payload={"uploaded_files": list(uploaded_files)},
                session_id=session_id,
                actor_id=actor_id,
                conversation_id=conversation_id,
            )
        )
        return present_execution(execution)

    async def index_status(self, task_id: str, *, session_id: str | None = None, actor_id: str | None = None) -> ApplicationView:
        execution = await self._runtime.execute(
            ApplicationRequest(
                capability=Capability.INDEX_STATUS,
                payload={"task_id": task_id},
                session_id=session_id,
                actor_id=actor_id,
            )
        )
        return present_execution(execution)

    async def history(self, conversation_id: str, *, actor_id: str, limit: int = 100) -> HistoryView:
        messages = await self._runtime.history(conversation_id, actor_id, limit=limit)
        return present_history(messages, conversation_id)
