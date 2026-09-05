"""Canonical application runtime boundary for the real user request journey.

The runtime owns request normalization, deterministic capability selection,
execution lifecycle instrumentation, evidence handoff, response shaping, and
optional conversation persistence. Provider-specific implementations are
injected behind small call contracts so this layer does not become coupled to
Azure, LlamaIndex, or a particular persistence provider.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Mapping

from .reliability import AgentObservability, Evidence
from .reliability.conversation import ConversationService, ConversationStore
from .reliability.contracts import ExecutionTrace


class Capability(StrEnum):
    """Capabilities exposed by the canonical application boundary."""

    QUESTION = "question"
    UPLOAD = "upload"
    INDEX_STATUS = "index_status"


@dataclass(frozen=True, slots=True)
class ApplicationRequest:
    """Normalized application input."""

    question: str = ""
    capability: Capability | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    actor_id: str | None = None
    conversation_id: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    """Deterministic capability-selection result."""

    capability: Capability
    reason: str


@dataclass(frozen=True, slots=True)
class ApplicationResult:
    """Stable response contract returned by the canonical runtime."""

    response_text: str
    capability: Capability
    metadata: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[Evidence, ...] = ()
    run_id: str = ""
    conversation_id: str | None = None


@dataclass(frozen=True, slots=True)
class ApplicationExecution:
    """Result plus trace for callers that need operational inspection."""

    result: ApplicationResult
    trace: ExecutionTrace


Handler = Callable[[ApplicationRequest], Any | Awaitable[Any]]


class ApplicationRuntime:
    """Single canonical boundary for application execution.

    Conversation persistence is opt-in through ``conversation_store``. When
    configured, question turns require actor/session/conversation identity,
    create the conversation if needed, and persist the successful user and
    assistant messages against the execution run.
    """

    def __init__(
        self,
        handlers: Mapping[Capability, Handler],
        *,
        observability: AgentObservability | None = None,
        conversation_store: ConversationStore | None = None,
    ) -> None:
        self._handlers = dict(handlers)
        self._observability = observability or AgentObservability()
        self._conversation_store = conversation_store

    @staticmethod
    def normalize(request: ApplicationRequest) -> ApplicationRequest:
        """Normalize whitespace while preserving payload semantics."""
        if not isinstance(request, ApplicationRequest):
            raise TypeError("request must be an ApplicationRequest")
        return ApplicationRequest(
            question=" ".join(request.question.split()),
            capability=request.capability,
            payload=dict(request.payload),
            session_id=request.session_id,
            actor_id=request.actor_id,
            conversation_id=request.conversation_id,
        )

    @staticmethod
    def decide(request: ApplicationRequest) -> CapabilityDecision:
        """Select a capability from explicit intent, never an LLM guess."""
        request = ApplicationRuntime.normalize(request)
        if request.capability is not None:
            if not isinstance(request.capability, Capability):
                raise TypeError("capability must be a Capability")
            return CapabilityDecision(request.capability, "explicit request capability")
        if not request.question:
            raise ValueError("question is required when capability is not explicit")
        return CapabilityDecision(Capability.QUESTION, "default question capability")

    async def execute(self, request: ApplicationRequest) -> ApplicationExecution:
        """Execute one request and return both stable result and trace."""
        normalized = self.normalize(request)
        decision = self.decide(normalized)
        handler = self._handlers.get(decision.capability)
        if handler is None:
            raise ValueError(f"no handler configured for capability: {decision.capability.value}")

        if self._conversation_store is not None and decision.capability is Capability.QUESTION:
            if not normalized.conversation_id or not normalized.actor_id or not normalized.session_id:
                raise ValueError("conversation_id, actor_id, and session_id are required when persistence is enabled")
            await ConversationService(self._conversation_store).ensure(
                normalized.conversation_id, normalized.actor_id, normalized.session_id
            )

        with self._observability.run(
            session_id=normalized.session_id,
            actor_id=normalized.actor_id,
            attributes={
                "capability": decision.capability.value,
                "conversation_id": normalized.conversation_id or "",
            },
        ) as trace:
            self._observability.record_event(
                trace,
                name="request.normalized",
                phase="normalization",
                attributes={"question_present": bool(normalized.question)},
                status="completed",
            )
            self._observability.record_event(
                trace,
                name="capability.selected",
                phase="decision",
                attributes={"capability": decision.capability.value, "reason": decision.reason},
                status="completed",
            )
            try:
                with self._observability.phase(trace, "capability.execute", "execution"):
                    raw = handler(normalized)
                    if isawaitable(raw):
                        raw = await raw
                result = self._coerce_result(raw, decision.capability, trace, normalized.conversation_id)
                if self._conversation_store is not None and decision.capability is Capability.QUESTION:
                    await ConversationService(self._conversation_store).record_turn(
                        normalized.conversation_id, normalized.actor_id,
                        question=normalized.question, answer=result.response_text, run_id=trace.run_id,
                    )
                    self._observability.record_event(
                        trace,
                        name="conversation.persisted",
                        phase="persistence",
                        attributes={"conversation_id": normalized.conversation_id},
                        status="completed",
                    )
                self._observability.record_event(
                    trace,
                    name="response.emitted",
                    phase="response",
                    attributes={"response_length": len(result.response_text)},
                    status="completed",
                )
                return ApplicationExecution(result=result, trace=trace)
            except Exception as exc:
                self._observability.record_event(
                    trace,
                    name="execution.error",
                    phase="execution",
                    status="error",
                    attributes={"error": type(exc).__name__},
                )
                raise

    async def history(self, conversation_id: str, actor_id: str, *, limit: int = 100):
        """Return persisted history when a conversation store is configured."""
        if self._conversation_store is None:
            raise RuntimeError("conversation persistence is not configured")
        return await ConversationService(self._conversation_store).history(conversation_id, actor_id, limit=limit)

    def _coerce_result(
        self,
        raw: Any,
        capability: Capability,
        trace: ExecutionTrace,
        conversation_id: str | None,
    ) -> ApplicationResult:
        if isinstance(raw, ApplicationResult):
            response_text = raw.response_text.strip()
            metadata = dict(raw.metadata)
            evidence = tuple(raw.evidence)
        elif isinstance(raw, str):
            response_text = raw.strip()
            metadata = {}
            evidence = ()
        elif isinstance(raw, Mapping):
            response_text = str(raw.get("response_text", "")).strip()
            metadata = dict(raw.get("metadata", {}))
            evidence = tuple(raw.get("evidence", ()))
        else:
            raise TypeError("handler must return str, ApplicationResult, or a mapping")

        if not response_text:
            raise ValueError("handler returned an empty response")
        for item in evidence:
            if not isinstance(item, Evidence):
                raise TypeError("handler evidence must contain Evidence objects")
            self._observability.record_evidence(
                trace,
                item,
                operation="application.retrieve",
                provider=str(item.metadata.get("provider")) if item.metadata.get("provider") else None,
            )
        return ApplicationResult(
            response_text=response_text,
            capability=capability,
            metadata={**metadata, **({"conversation_id": conversation_id} if conversation_id else {})},
            evidence=evidence,
            run_id=trace.run_id,
            conversation_id=conversation_id,
        )
