"""Provider-neutral operational failure triage derived from existing retrospective facts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from .background import FailureClass
from .retrospective import Retrospective


class TriagePriority(StrEnum):
    """Deterministic incident handling priority."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class TriageItem:
    """Bounded diagnosis item linked to an existing retrospective finding."""

    item_id: str
    category: str
    priority: TriagePriority
    summary: str
    action: str
    finding_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FailureTriage:
    """Deterministic operational diagnosis view over one retrospective."""

    run_id: str
    outcome: str
    priority: TriagePriority
    items: tuple[TriageItem, ...]

    @property
    def requires_operator(self) -> bool:
        return self.priority in {TriagePriority.CRITICAL, TriagePriority.HIGH}


class FailureTriageEngine:
    """Convert existing retrospective findings into actionable bounded triage."""

    def analyze(self, retrospective: Retrospective) -> FailureTriage:
        if not isinstance(retrospective, Retrospective):
            raise TypeError("retrospective must be a Retrospective")

        items: list[TriageItem] = []
        for finding in retrospective.findings:
            priority = _priority_for_finding(finding.category, finding.severity, retrospective.outcome)
            action = _action_for_category(finding.category)
            items.append(
                TriageItem(
                    item_id=f"triage-{len(items) + 1}",
                    category=finding.category,
                    priority=priority,
                    summary=_bounded(finding.summary),
                    action=_bounded(action),
                    finding_ids=(finding.finding_id,),
                )
            )

        items.sort(key=lambda item: (_priority_rank(item.priority), item.item_id))
        overall = _highest_priority((item.priority for item in items), retrospective.outcome)
        return FailureTriage(
            run_id=_bounded(retrospective.run_id),
            outcome=_bounded(retrospective.outcome),
            priority=overall,
            items=tuple(items),
        )


def _priority_for_finding(category: str, severity: str, outcome: str) -> TriagePriority:
    if outcome == "error" and severity == "high":
        return TriagePriority.CRITICAL
    if category == "execution" and severity == "high":
        return TriagePriority.CRITICAL
    if severity == "high":
        return TriagePriority.HIGH
    if severity == "medium":
        return TriagePriority.MEDIUM
    return TriagePriority.LOW


def _action_for_category(category: str) -> str:
    return {
        "execution": "inspect the failing lifecycle phase and provider boundary",
        "evidence": "verify evidence collection and grounding before releasing the response",
        "retrieval": "inspect retrieval filters, query construction, and corpus coverage",
        "lifecycle": "inspect the failed phase and recovery path",
        "response": "inspect response emission and success-state ordering",
    }.get(category, "inspect the recorded finding and associated execution facts")


def _highest_priority(priorities: Iterable[TriagePriority], outcome: str) -> TriagePriority:
    values = tuple(priorities)
    if values:
        return min(values, key=_priority_rank)
    if outcome == "error":
        return TriagePriority.HIGH
    return TriagePriority.LOW


def _priority_rank(priority: TriagePriority) -> int:
    return {
        TriagePriority.CRITICAL: 0,
        TriagePriority.HIGH: 1,
        TriagePriority.MEDIUM: 2,
        TriagePriority.LOW: 3,
    }[priority]


def _bounded(value: str, limit: int = 256) -> str:
    return str(value)[:limit]
