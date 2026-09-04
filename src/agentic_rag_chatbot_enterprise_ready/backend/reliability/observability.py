"""Runtime instrumentation facade with no vendor lock-in."""
from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Iterator

from .contracts import ExecutionEvent, ExecutionTrace, Evidence, EvidenceRecord, ProvenanceRecord
from .store import InMemoryReliabilityStore


class AgentObservability:
    """Record execution phases, evidence, and provenance as structured facts."""

    def __init__(self, store: InMemoryReliabilityStore | None = None) -> None:
        self.store = store or InMemoryReliabilityStore()

    @contextmanager
    def run(self, *, attributes: dict[str, Any] | None = None) -> Iterator[ExecutionTrace]:
        trace = ExecutionTrace()
        trace.add_event(ExecutionEvent("agent.run", "execution", "started", trace.run_id, attributes=attributes or {}))
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
    def phase(self, trace: ExecutionTrace, name: str, phase: str, *, attributes: dict[str, Any] | None = None):
        started = perf_counter()
        trace.add_event(ExecutionEvent(name, phase, "started", trace.run_id, attributes=attributes or {}))
        try:
            yield
        except Exception as exc:
            trace.add_event(ExecutionEvent(name, phase, "error", trace.run_id, duration_ms=(perf_counter() - started) * 1000, attributes={"error": str(exc), **(attributes or {})}))
            raise
        else:
            trace.add_event(ExecutionEvent(name, phase, "success", trace.run_id, duration_ms=(perf_counter() - started) * 1000, attributes=attributes or {}))

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
