"""Controlled, provider-neutral benchmarking of agent architectures."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from typing import Any, Protocol

from .contracts import Evidence, ExecutionEvent, ExecutionTrace
from .harness import HarnessCase, HarnessEngine, HarnessResult


@dataclass(frozen=True, slots=True)
class BenchmarkContext:
    """Immutable inputs shared by every architecture for one benchmark case."""

    case: HarnessCase
    available_evidence: tuple[Evidence, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArchitectureSpec:
    """Identity and human-readable description of an architecture variant."""

    architecture_id: str
    version: str = "1"
    description: str = ""


class ArchitectureAdapter(Protocol):
    """Architecture contract used by the benchmark harness."""

    spec: ArchitectureSpec

    async def execute(self, context: BenchmarkContext) -> Any:
        """Execute against the benchmark context and return a harness-compatible value."""
        ...


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    """Comparable execution metrics derived from deterministic execution facts."""

    passed: bool
    grounding_coverage: float
    retrieval_relevance: float
    latency_ms: float
    model_calls: int
    tool_calls: int
    retrieval_calls: int
    error: bool
    provenance_completeness: float


@dataclass(frozen=True, slots=True)
class ArchitectureBenchmarkRun:
    """One architecture execution for one scenario."""

    scenario_id: str
    architecture: ArchitectureSpec
    run_index: int
    harness_result: HarnessResult
    metrics: BenchmarkMetrics


@dataclass(frozen=True, slots=True)
class ArchitectureAggregate:
    """Aggregate results for one architecture over equivalent scenario runs."""

    architecture: ArchitectureSpec
    runs: int
    pass_rate: float
    average_grounding_coverage: float
    average_retrieval_relevance: float
    average_latency_ms: float
    average_model_calls: float
    average_tool_calls: float
    average_retrieval_calls: float
    error_rate: float
    average_provenance_completeness: float


class ArchitectureBenchmark:
    """Run architecture variants under the same scenarios and evaluation rules."""

    def __init__(self, harness: HarnessEngine | None = None) -> None:
        self.harness = harness or HarnessEngine()

    async def run(
        self,
        contexts: Iterable[BenchmarkContext],
        architectures: Iterable[ArchitectureAdapter],
        repetitions: int = 1,
    ) -> tuple[ArchitectureBenchmarkRun, ...]:
        contexts = tuple(contexts)
        architectures = tuple(architectures)
        if repetitions < 1:
            raise ValueError("repetitions must be >= 1")
        self._validate_inputs(contexts, architectures)
        results: list[ArchitectureBenchmarkRun] = []
        for context in contexts:
            for adapter in architectures:
                for run_index in range(1, repetitions + 1):
                    result, trace = await self._run_adapter(context, adapter)
                    results.append(
                        ArchitectureBenchmarkRun(
                            context.case.case_id,
                            adapter.spec,
                            run_index,
                            result,
                            self._metrics(result, trace),
                        )
                    )
        return tuple(results)

    @staticmethod
    def aggregate(results: Iterable[ArchitectureBenchmarkRun]) -> tuple[ArchitectureAggregate, ...]:
        grouped: dict[tuple[str, str], list[ArchitectureBenchmarkRun]] = {}
        for result in results:
            grouped.setdefault((result.architecture.architecture_id, result.architecture.version), []).append(result)
        aggregates: list[ArchitectureAggregate] = []
        for group in grouped.values():
            first = group[0].architecture
            aggregates.append(
                ArchitectureAggregate(
                    architecture=first,
                    runs=len(group),
                    pass_rate=mean(r.metrics.passed for r in group),
                    average_grounding_coverage=mean(r.metrics.grounding_coverage for r in group),
                    average_retrieval_relevance=mean(r.metrics.retrieval_relevance for r in group),
                    average_latency_ms=mean(r.metrics.latency_ms for r in group),
                    average_model_calls=mean(r.metrics.model_calls for r in group),
                    average_tool_calls=mean(r.metrics.tool_calls for r in group),
                    average_retrieval_calls=mean(r.metrics.retrieval_calls for r in group),
                    error_rate=mean(r.metrics.error for r in group),
                    average_provenance_completeness=mean(r.metrics.provenance_completeness for r in group),
                )
            )
        return tuple(aggregates)

    async def _run_adapter(
        self, context: BenchmarkContext, adapter: ArchitectureAdapter
    ) -> tuple[HarnessResult, ExecutionTrace]:
        async def executor(question: str) -> Any:
            raw = await adapter.execute(context)
            self._validate_output_evidence(context, raw)
            return raw

        result = await self.harness.run_case(context.case, executor)
        trace = self.harness.store.get(result.run_id)
        if trace is None:
            raise RuntimeError(f"benchmark trace was not persisted: {result.run_id}")
        return result, trace

    @staticmethod
    def _metrics(result: HarnessResult, trace: ExecutionTrace) -> BenchmarkMetrics:
        events = trace.events
        model_calls = sum(1 for event in events if event.name == "model.call")
        tool_calls = sum(1 for event in events if event.name == "tool.call")
        retrieval_calls = sum(1 for event in events if event.name == "retrieval")
        provenance_complete = (
            sum(bool(record.provenance.record_id) for record in trace.evidence) / len(trace.evidence)
            if trace.evidence
            else 1.0
        )
        latency = 0.0
        if trace.started_at and trace.finished_at:
            try:
                started = datetime.fromisoformat(trace.started_at.replace("Z", "+00:00"))
                finished = datetime.fromisoformat(trace.finished_at.replace("Z", "+00:00"))
                latency = max(0.0, (finished - started).total_seconds() * 1000)
            except ValueError:
                latency = 0.0
        return BenchmarkMetrics(
            passed=result.passed,
            grounding_coverage=result.grounding_coverage,
            retrieval_relevance=result.retrieval_relevance,
            latency_ms=latency,
            model_calls=model_calls,
            tool_calls=tool_calls,
            retrieval_calls=retrieval_calls,
            error=result.outcome == "error",
            provenance_completeness=provenance_complete,
        )

    @staticmethod
    def _validate_inputs(contexts: tuple[BenchmarkContext, ...], architectures: tuple[ArchitectureAdapter, ...]) -> None:
        if not contexts:
            raise ValueError("at least one benchmark context is required")
        if not architectures:
            raise ValueError("at least one architecture is required")
        case_ids = [context.case.case_id for context in contexts]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("benchmark contexts must have unique case ids")
        architecture_ids = [(a.spec.architecture_id, a.spec.version) for a in architectures]
        if len(architecture_ids) != len(set(architecture_ids)):
            raise ValueError("architecture identity must be unique")

    @staticmethod
    def _validate_output_evidence(context: BenchmarkContext, value: Any) -> None:
        raw_evidence = value.get("evidence", ()) if isinstance(value, dict) else getattr(value, "evidence", ())
        available_ids = {e.source_id for e in context.available_evidence}
        if not available_ids:
            return
        for item in raw_evidence or ():
            source_id = item.evidence.source_id if hasattr(item, "evidence") else getattr(item, "source_id", None)
            if source_id not in available_ids:
                raise ValueError(f"architecture returned evidence outside benchmark fixture: {source_id!r}")
        if any(not evidence.source_id for evidence in context.available_evidence):
            raise ValueError("available evidence source_id must be non-empty")
