"""Provider-neutral UI/API surface over the canonical application runtime."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence
from ..backend.application_runtime import ApplicationExecution, ApplicationRequest, ApplicationRuntime, Capability
from ..backend.reliability import ConversationMessage, Evidence
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
    def to_dict(self) -> dict[str, Any]: return asdict(self)
@dataclass(frozen=True, slots=True)
class HistoryView:
    messages: tuple[dict[str, Any], ...]
    conversation_id: str
    def to_dict(self) -> dict[str, Any]: return {"conversation_id": self.conversation_id, "messages": list(self.messages)}
def present_execution(execution: ApplicationExecution) -> ApplicationView:
    result = execution.result
    return ApplicationView(result.response_text, result.capability.value, result.run_id, result.conversation_id, tuple(EvidenceView(i.source, i.locator, dict(i.metadata)) for i in result.evidence), dict(result.metadata))
def present_history(messages: Sequence[ConversationMessage], conversation_id: str) -> HistoryView:
    return HistoryView(conversation_id, tuple({"message_id": i.message_id, "role": i.role, "content": i.content, "created_at": i.created_at, "run_id": i.run_id, "metadata": dict(i.metadata)} for i in messages))
class ApplicationSurface:
    def __init__(self, runtime: ApplicationRuntime) -> None: self._runtime = runtime
    async def question(self, question: str, *, session_id: str, actor_id: str, conversation_id: str, payload: Mapping[str, Any] | None = None) -> ApplicationView:
        return present_execution(await self._runtime.execute(ApplicationRequest(question=question, capability=Capability.QUESTION, payload=dict(payload or {}), session_id=session_id, actor_id=actor_id, conversation_id=conversation_id)))
    async def upload(self, uploaded_files: Sequence[Mapping[str, Any]], *, session_id: str, actor_id: str, conversation_id: str | None = None) -> ApplicationView:
        return present_execution(await self._runtime.execute(ApplicationRequest(capability=Capability.UPLOAD, payload={"uploaded_files": list(uploaded_files)}, session_id=session_id, actor_id=actor_id, conversation_id=conversation_id)))
    async def index_status(self, task_id: str, *, session_id: str | None = None, actor_id: str | None = None) -> ApplicationView:
        return present_execution(await self._runtime.execute(ApplicationRequest(capability=Capability.INDEX_STATUS, payload={"task_id": task_id}, session_id=session_id, actor_id=actor_id)))
    async def history(self, conversation_id: str, *, actor_id: str, limit: int = 100) -> HistoryView:
        return present_history(await self._runtime.history(conversation_id, actor_id, limit=limit), conversation_id)
