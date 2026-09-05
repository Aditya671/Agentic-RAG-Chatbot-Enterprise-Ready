"""Provider-neutral UI/API surface over the canonical application runtime."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from ..backend.application_runtime import (
    ApplicationExecution,
    ApplicationRequest,
    ApplicationRuntime,
    Capability,
)
from ..backend.reliability import ConversationMessage


@dataclass(frozen=True, slots=True)
class EvidenceView:
    source: str
    locator: str | None
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ApplicationView:
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
    messages: tuple[dict[str, Any], ...]
    conversation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "messages": list(self.messages),
        }


def present_execution(execution: ApplicationExecution) -> ApplicationView:
    result = execution.result
    return ApplicationView(
        response_text=result.response_text,
        capability=result.capability.value,
        run_id=result.run_id,
        conversation_id=result.conversation_id,
        evidence=tuple(
            EvidenceView(
                item.source_id,
                item.locator,
                dict(item.metadata),
            )
            for item in result.evidence
        ),
        metadata=dict(result.metadata),
    )


def present_history(
    messages: Sequence[ConversationMessage], conversation_id: str
) -> HistoryView:
    return HistoryView(
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
        conversation_id=conversation_id,
    )


class ApplicationSurface:
    """Thin client-facing projection over the canonical application runtime."""

    def __init__(self, runtime: ApplicationRuntime) -> None:
        self._runtime = runtime

    async def question(
        self,
        question: str,
        *,
        session_id: str,
        actor_id: str,
        conversation_id: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ApplicationView:
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

    async def upload(
        self,
        uploaded_files: Sequence[Mapping[str, Any]],
        *,
        session_id: str,
        actor_id: str,
        conversation_id: str | None = None,
    ) -> ApplicationView:
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

    async def index_status(
        self,
        task_id: str,
        *,
        session_id: str | None = None,
        actor_id: str | None = None,
    ) -> ApplicationView:
        execution = await self._runtime.execute(
            ApplicationRequest(
                capability=Capability.INDEX_STATUS,
                payload={"task_id": task_id},
                session_id=session_id,
                actor_id=actor_id,
            )
        )
        return present_execution(execution)

    async def history(
        self,
        conversation_id: str,
        *,
        actor_id: str,
        limit: int = 100,
    ) -> HistoryView:
        messages = await self._runtime.history(
            conversation_id,
            actor_id,
            limit=limit,
        )
        return present_history(messages, conversation_id)
