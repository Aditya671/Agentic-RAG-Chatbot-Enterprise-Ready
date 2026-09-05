"""Canonical application runtime boundary for the real user request journey.

The runtime owns request normalization, deterministic capability selection,
execution lifecycle instrumentation, evidence handoff, and response shaping.
Provider-specific implementations are injected behind small call contracts so
this layer does not become coupled to Azure, LlamaIndex, or a particular tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Mapping

from .reliability import AgentObservability, Evidence
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


@dataclass(frozen=True, slots=True)
class ApplicationExecution:
    """Result plus trace for callers that need operational inspection."""

    result: ApplicationResult
    trace: ExecutionTrace


Handler = Callable[[ApplicationRequest], Any | Awaitable[Any]]


class ApplicationRuntime:
    """Single canonical boundary for application execution.

    Handlers may return a string, an ``ApplicationResult``, or a mapping with
    ``response_text``, optional ``metadata``, and optional ``evidence``.
    Evidence is validated and recorded through the existing observability
    layer rather than allowing providers to define their own telemetry model.
    """

    def __init__(
        self,
        handlers: Mapping[Capability, Handler],
        *,
        observability: AgentObservability | None = None,
    ) -> None:
        self._handlers = dict(handlers)
        self._observability = observability or AgentObservability()

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

        with self._observability.run(
            session_id=normalized.session_id,
            actor_id=normalized.actor_id,
            attributes={"capability": decision.capability.value},
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
                result = self._coerce_result(raw, decision.capability, trace)
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

    def _coerce_result(
        self,
        raw: Any,
        capability: Capability,
        trace: ExecutionTrace,
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
            metadata=metadata,
            evidence=evidence,
            run_id=trace.run_id,
        )
