"""Execution harness for deterministic agent scenarios."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable

from .contracts import Evidence, EvidenceRecord, ExecutionEvent, ExecutionTrace, ProvenanceRecord
from .scenario_evaluation import ScenarioEvaluationEngine
from .store import InMemoryReliabilityStore


@dataclass(frozen=True, slots=True)
class HarnessCase:
    case_id: str
    question: str
    expected_text_contains: tuple[str, ...] = ()
    expected_outcome: str = "success"
    expected_evidence_source_ids: tuple[str, ...] = ()
    min_evidence_relevance: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HarnessResult:
    case_id: str
    passed: bool
    outcome: str
    response_text: str = ""
    failures: tuple[str, ...] = ()
    run_id: str = ""
    grounding_coverage: float = 0.0
    retrieval_relevance: float = 0.0


class ScenarioCatalog:
    """Deterministic registry for named regression scenarios."""

    def __init__(self, cases: Iterable[HarnessCase] = ()) -> None:
        self._cases: dict[str, HarnessCase] = {}
        for case in cases:
            self.add(case)

    def add(self, case: HarnessCase) -> None:
        if not isinstance(case, HarnessCase):
            raise TypeError("case must be a HarnessCase")
        if not case.case_id.strip():
            raise ValueError("case.case_id must be non-empty")
        if case.case_id in self._cases:
            raise ValueError(f"scenario already exists: {case.case_id}")
        self._cases[case.case_id] = case

    def get(self, case_id: str) -> HarnessCase:
        try:
            return self._cases[case_id]
        except KeyError as exc:
            raise KeyError(f"unknown scenario: {case_id}") from exc

    def cases(self) -> tuple[HarnessCase, ...]:
        return tuple(self._cases.values())


class HarnessEngine:
    """Run an agent callable while capturing a trace and explicit assertions."""

    def __init__(self, store: InMemoryReliabilityStore | None = None) -> None:
        self.store = store or InMemoryReliabilityStore()

    async def run_case(
        self,
        case: HarnessCase,
        executor: Callable[[str], Awaitable[Any]],
    ) -> HarnessResult:
        if not isinstance(case.question, str) or not case.question.strip():
            raise ValueError("case.question must be non-empty")
        trace = ExecutionTrace()
        trace.add_event(ExecutionEvent(name="agent.run", phase="execution", run_id=trace.run_id))
        try:
            raw = await executor(case.question)
            response_text = self._extract_text(raw)
            self._record_evidence(trace, raw)
            evaluation = ScenarioEvaluationEngine.evaluate(case, trace, response_text)
            failures = evaluation.failures
            outcome = "success" if not failures else "assertion_failed"
            if case.expected_outcome != outcome:
                failures += (f"expected outcome {case.expected_outcome!r}, got {outcome!r}",)
            trace.add_event(ExecutionEvent(name="agent.run", phase="execution", status=outcome, run_id=trace.run_id))
            trace.finish("success" if not failures else "failure")
            return HarnessResult(
                case.case_id,
                not failures,
                outcome,
                response_text,
                failures,
                trace.run_id,
                evaluation.grounding_coverage,
                evaluation.retrieval_relevance,
            )
        except Exception as exc:
            trace.add_event(ExecutionEvent(name="agent.run", phase="execution", status="error", run_id=trace.run_id, attributes={"error_type": type(exc).__name__}))
            trace.finish("error", str(exc))
            if case.expected_outcome == "error":
                return HarnessResult(case.case_id, True, "error", failures=(), run_id=trace.run_id)
            return HarnessResult(case.case_id, False, "error", failures=(str(exc),), run_id=trace.run_id)
        finally:
            self.store.save(trace)

    async def replay(self, case_id: str, catalog: ScenarioCatalog, executor: Callable[[str], Awaitable[Any]]) -> HarnessResult:
        """Replay a named scenario using its immutable expectations."""
        return await self.run_case(catalog.get(case_id), executor)

    async def replay_all(self, catalog: ScenarioCatalog, executor: Callable[[str], Awaitable[Any]]) -> tuple[HarnessResult, ...]:
        """Replay scenarios in registration order for deterministic regression runs."""
        return tuple(await self.replay(case.case_id, catalog, executor) for case in catalog.cases())

    @staticmethod
    def _extract_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("response_text", "response", "text"):
                if value.get(key) is not None:
                    return str(value[key])
        for attr in ("response_text", "response", "text"):
            result = getattr(value, attr, None)
            if result is not None:
                return str(result)
        return str(value)

    @staticmethod
    def _record_evidence(trace: ExecutionTrace, value: Any) -> None:
        """Accept explicit evidence from deterministic executors without parsing prose."""
        raw_evidence = value.get("evidence", ()) if isinstance(value, dict) else getattr(value, "evidence", ())
        for item in raw_evidence or ():
            if isinstance(item, EvidenceRecord):
                trace.add_evidence(item)
                continue
            if not isinstance(item, Evidence):
                raise TypeError("executor evidence must contain Evidence or EvidenceRecord instances")
            trace.add_evidence(
                EvidenceRecord(
                    item,
                    ProvenanceRecord(
                        record_id=f"prov-{item.source_id}-{len(trace.evidence) + 1}",
                        operation="retrieval",
                    ),
                )
            )
