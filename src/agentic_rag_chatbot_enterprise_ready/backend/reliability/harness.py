"""Execution harness for deterministic agent scenarios."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .contracts import ExecutionEvent, ExecutionTrace
from .store import InMemoryReliabilityStore


@dataclass(frozen=True, slots=True)
class HarnessCase:
    case_id: str
    question: str
    expected_text_contains: tuple[str, ...] = ()
    expected_outcome: str = "success"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HarnessResult:
    case_id: str
    passed: bool
    outcome: str
    response_text: str = ""
    failures: tuple[str, ...] = ()
    run_id: str = ""


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
            failures = tuple(
                f"response missing expected text: {expected!r}"
                for expected in case.expected_text_contains
                if expected.casefold() not in response_text.casefold()
            )
            outcome = "success" if not failures else "assertion_failed"
            if case.expected_outcome != outcome:
                failures += (f"expected outcome {case.expected_outcome!r}, got {outcome!r}",)
            trace.add_event(ExecutionEvent(name="agent.run", phase="execution", status=outcome, run_id=trace.run_id))
            trace.finish("success" if not failures else "failure")
            return HarnessResult(case.case_id, not failures, outcome, response_text, failures, trace.run_id)
        except Exception as exc:
            trace.add_event(ExecutionEvent(name="agent.run", phase="execution", status="error", run_id=trace.run_id, attributes={"error_type": type(exc).__name__}))
            trace.finish("error", str(exc))
            if case.expected_outcome == "error":
                return HarnessResult(case.case_id, True, "error", failures=(), run_id=trace.run_id)
            return HarnessResult(case.case_id, False, "error", failures=(str(exc),), run_id=trace.run_id)
        finally:
            self.store.save(trace)

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
