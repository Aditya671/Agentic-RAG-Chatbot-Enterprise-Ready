"""Versioned, serializable scenario definitions for architecture benchmarks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .harness import HarnessCase


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    """A named benchmark scenario with explicit version and immutable expectations."""

    scenario_id: str
    version: str
    case: HarnessCase
    difficulty: str = "standard"
    tags: tuple[str, ...] = ()
    expected_capabilities: tuple[str, ...] = ()
    fixture_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id must be non-empty")
        if not self.version.strip():
            raise ValueError("version must be non-empty")
        if self.case.case_id != self.scenario_id:
            raise ValueError("case.case_id must match scenario_id")
        if self.difficulty not in {"basic", "standard", "advanced", "failure", "recovery"}:
            raise ValueError("unsupported scenario difficulty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "version": self.version,
            "difficulty": self.difficulty,
            "tags": list(self.tags),
            "expected_capabilities": list(self.expected_capabilities),
            "fixture_ids": list(self.fixture_ids),
            "question": self.case.question,
            "expected_text_contains": list(self.case.expected_text_contains),
            "expected_outcome": self.case.expected_outcome,
            "expected_evidence_source_ids": list(self.case.expected_evidence_source_ids),
            "min_evidence_relevance": self.case.min_evidence_relevance,
            "metadata": dict(self.metadata),
        }


class BenchmarkScenarioCatalog:
    """Registry enforcing unique scenario/version identities."""

    def __init__(self, scenarios: tuple[BenchmarkScenario, ...] = ()) -> None:
        self._scenarios: dict[tuple[str, str], BenchmarkScenario] = {}
        for scenario in scenarios:
            self.add(scenario)

    def add(self, scenario: BenchmarkScenario) -> None:
        if not isinstance(scenario, BenchmarkScenario):
            raise TypeError("scenario must be a BenchmarkScenario")
        key = (scenario.scenario_id, scenario.version)
        if key in self._scenarios:
            raise ValueError(f"scenario version already exists: {key!r}")
        self._scenarios[key] = scenario

    def get(self, scenario_id: str, version: str) -> BenchmarkScenario:
        try:
            return self._scenarios[(scenario_id, version)]
        except KeyError as exc:
            raise KeyError(f"unknown scenario version: {scenario_id!r}/{version!r}") from exc

    def scenarios(self) -> tuple[BenchmarkScenario, ...]:
        return tuple(self._scenarios.values())
