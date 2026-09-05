"""Runtime instrumentation facade with no vendor lock-in."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from .contracts import Evidence, EvidenceRecord, ExecutionEvent, ExecutionTrace, ProvenanceRecord
from .store import InMemoryReliabilityStore


class AgentObservability:
    """Record execution phases, evidence, and provenance as structured facts."""

    def __init__(self, store: InMemoryReliabilityStore | None = None) -> None:
        self.store = store or InMemoryReliabilityStore()

    @contextmanager
    def run(
        self,
        *,
        request_id: str | None = None,
        session_id: str | None = None,
        actor_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[ExecutionTrace]:
        """Create a correlated run without recording prompts, content, or raw PII."""
        trace = ExecutionTrace(request_id=request_id or str(uuid.uuid4()), session_id=session_id, actor_id=actor_id)
        event_attributes = {
            "request_id": trace.request_id,
            "session_id": trace.session_id,
            "actor_id": trace.actor_id,
            **(attributes or {}),
        }
        trace.add_event(ExecutionEvent("agent.run", "execution", "started", trace.run_id, attributes=event_attributes))
        try:
            yield trace
        except Exception as exc:
            trace.finish("error", str(exc))
            raise
        else:
            trace.finish("success")
        finally:
            self.store.save(trace)

    @contextmanager
    def phase(
        self,
        trace: ExecutionTrace,
        name: str,
        phase: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[None]:
        """Capture one lifecycle operation; callers should pass metadata, not payloads."""
        started = perf_counter()
        trace.add_event(ExecutionEvent(name, phase, "started", trace.run_id, attributes=attributes or {}))
        try:
            yield
        except Exception as exc:
            trace.add_event(
                ExecutionEvent(
                    name,
                    phase,
                    "error",
                    trace.run_id,
                    duration_ms=(perf_counter() - started) * 1000,
                    attributes={"error_type": type(exc).__name__, **(attributes or {})},
                )
            )
            raise
        else:
            trace.add_event(
                ExecutionEvent(
                    name,
                    phase,
                    "success",
                    trace.run_id,
                    duration_ms=(perf_counter() - started) * 1000,
                    attributes=attributes or {},
                )
            )

    def record_event(
        self,
        trace: ExecutionTrace,
        *,
        name: str,
        phase: str,
        status: str = "success",
        attributes: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> str:
        """Record a structured lifecycle fact and return its event id."""
        event = ExecutionEvent(
            name=name,
            phase=phase,
            status=status,
            run_id=trace.run_id,
            duration_ms=duration_ms,
            attributes=attributes or {},
        )
        trace.add_event(event)
        return event.event_id

    def record_evidence(
        self,
        trace: ExecutionTrace,
        evidence: Evidence,
        *,
        operation: str = "retrieval",
        provider: str | None = None,
        parent_ids: tuple[str, ...] = (),
    ) -> str:
        provenance_id = f"prov-{evidence.source_id}-{len(trace.evidence) + 1}"
        trace.add_evidence(EvidenceRecord(evidence, ProvenanceRecord(provenance_id, parent_ids, operation, provider=provider)))
        return provenance_id

    def record_retrieval(
        self,
        trace: ExecutionTrace,
        evidence: tuple[Evidence, ...],
        *,
        provider: str | None = None,
        duration_ms: float | None = None,
    ) -> tuple[str, ...]:
        """Record retrieval metadata and its evidence/provenance without storing a query payload."""
        provenance_ids = tuple(self.record_evidence(trace, item, provider=provider) for item in evidence)
        self.record_event(
            trace,
            name="retrieval.search",
            phase="retrieval",
            attributes={"provider": provider, "result_count": len(evidence)},
            duration_ms=duration_ms,
        )
        return provenance_ids

    def record_tool_call(
        self,
        trace: ExecutionTrace,
        *,
        tool: str,
        status: str = "success",
        duration_ms: float | None = None,
        arguments_hash: str | None = None,
        result_summary: str | None = None,
    ) -> str:
        """Record tool metadata while explicitly excluding raw arguments and results."""
        attributes: dict[str, Any] = {"tool": tool}
        if arguments_hash is not None:
            attributes["arguments_hash"] = arguments_hash
        if result_summary is not None:
            attributes["result_summary"] = result_summary
        return self.record_event(trace, name=f"tool.{tool}", phase="tool", status=status, attributes=attributes, duration_ms=duration_ms)

    def record_model_call(
        self,
        trace: ExecutionTrace,
        *,
        provider: str,
        model: str,
        status: str = "success",
        duration_ms: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> str:
        attributes: dict[str, Any] = {"provider": provider, "model": model}
        if input_tokens is not None:
            attributes["input_tokens"] = input_tokens
        if output_tokens is not None:
            attributes["output_tokens"] = output_tokens
        return self.record_event(trace, name="model.call", phase="model", status=status, attributes=attributes, duration_ms=duration_ms)

    def record_response(
        self,
        trace: ExecutionTrace,
        *,
        status: str = "success",
        response_hash: str | None = None,
        response_length: int | None = None,
    ) -> str:
        """Record response metadata without storing the response body."""
        attributes: dict[str, Any] = {}
        if response_hash is not None:
            attributes["response_hash"] = response_hash
        if response_length is not None:
            attributes["response_length"] = response_length
        return self.record_event(trace, name="agent.response", phase="response", status=status, attributes=attributes)
