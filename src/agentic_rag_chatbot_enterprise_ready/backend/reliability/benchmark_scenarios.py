"""Versioned, serializable scenario and fixture definitions for benchmarks."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .claims import Claim, ClaimEvidenceLink
from .contracts import EvidenceRecord
from .harness import HarnessCase


@dataclass(frozen=True, slots=True)
class BenchmarkEvidenceFixture:
    """Immutable evidence fixture identified by a stable fixture/version pair."""

    fixture_id: str
    version: str
    evidence: tuple[EvidenceRecord, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ValueError("fixture_id must be non-empty")
        if not self.version.strip():
            raise ValueError("version must be non-empty")
        if not isinstance(self.evidence, tuple) or not all(
            isinstance(record, EvidenceRecord) for record in self.evidence
        ):
            raise TypeError("evidence must be a tuple of EvidenceRecord instances")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkFixtureCatalog:
    """Registry enforcing unique fixture/version identities."""

    def __init__(self, fixtures: tuple[BenchmarkEvidenceFixture, ...] = ()) -> None:
        self._fixtures: dict[tuple[str, str], BenchmarkEvidenceFixture] = {}
        for fixture in fixtures:
            self.add(fixture)

    def add(self, fixture: BenchmarkEvidenceFixture) -> None:
        if not isinstance(fixture, BenchmarkEvidenceFixture):
            raise TypeError("fixture must be a BenchmarkEvidenceFixture")
        key = (fixture.fixture_id, fixture.version)
        if key in self._fixtures:
            raise ValueError(f"fixture version already exists: {key!r}")
        self._fixtures[key] = fixture

    def get(self, fixture_id: str, version: str) -> BenchmarkEvidenceFixture:
        try:
            return self._fixtures[(fixture_id, version)]
        except KeyError as exc:
            raise KeyError(f"unknown fixture version: {fixture_id!r}/{version!r}") from exc

    def fixtures(self) -> tuple[BenchmarkEvidenceFixture, ...]:
        return tuple(self._fixtures.values())


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    """A named benchmark scenario with explicit version and immutable expectations."""

    scenario_id: str
    version: str
    case: HarnessCase
    difficulty: str = "standard"
    tags: tuple[str, ...] = ()
    expected_capabilities: tuple[str, ...] = ()
    fixture_refs: tuple[tuple[str, str], ...] = ()
    expected_claims: tuple[Claim, ...] = ()
    expected_claim_evidence_links: tuple[ClaimEvidenceLink, ...] = ()
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
        if any(
            not fixture_id.strip() or not fixture_version.strip()
            for fixture_id, fixture_version in self.fixture_refs
        ):
            raise ValueError("fixture references require non-empty ID and version")
        if len(self.fixture_refs) != len(set(self.fixture_refs)):
            raise ValueError("fixture references must be unique")
        if not all(isinstance(claim, Claim) for claim in self.expected_claims):
            raise TypeError("expected_claims must contain Claim instances")
        if not all(isinstance(link, ClaimEvidenceLink) for link in self.expected_claim_evidence_links):
            raise TypeError("expected_claim_evidence_links must contain ClaimEvidenceLink instances")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "version": self.version,
            "difficulty": self.difficulty,
            "tags": list(self.tags),
            "expected_capabilities": list(self.expected_capabilities),
            "fixture_refs": [list(ref) for ref in self.fixture_refs],
            "question": self.case.question,
            "expected_text_contains": list(self.case.expected_text_contains),
            "expected_outcome": self.case.expected_outcome,
            "expected_evidence_source_ids": list(self.case.expected_evidence_source_ids),
            "min_evidence_relevance": self.case.min_evidence_relevance,
            "expected_claims": [
                {
                    "claim_id": claim.claim_id,
                    "text": claim.text,
                    "required_evidence_source_ids": list(claim.required_evidence_source_ids),
                    "metadata": dict(claim.metadata),
                }
                for claim in self.expected_claims
            ],
            "expected_claim_evidence_links": [
                {
                    "claim_id": link.claim_id,
                    "evidence_source_id": link.evidence_source_id,
                    "relationship": link.relationship,
                    "metadata": dict(link.metadata),
                }
                for link in self.expected_claim_evidence_links
            ],
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


@dataclass(frozen=True, slots=True)
class BenchmarkDataset:
    """A versioned, self-contained benchmark dataset boundary."""

    dataset_id: str
    version: str
    scenarios: tuple[BenchmarkScenario, ...]
    fixtures: tuple[BenchmarkEvidenceFixture, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.version.strip():
            raise ValueError("dataset_id and version must be non-empty")
        if not isinstance(self.scenarios, tuple) or not all(
            isinstance(scenario, BenchmarkScenario) for scenario in self.scenarios
        ):
            raise TypeError("scenarios must be a tuple of BenchmarkScenario instances")
        if not isinstance(self.fixtures, tuple) or not all(
            isinstance(fixture, BenchmarkEvidenceFixture) for fixture in self.fixtures
        ):
            raise TypeError("fixtures must be a tuple of BenchmarkEvidenceFixture instances")

        scenario_keys = [(scenario.scenario_id, scenario.version) for scenario in self.scenarios]
        if len(scenario_keys) != len(set(scenario_keys)):
            raise ValueError("dataset contains duplicate scenario/version identities")
        fixture_keys = [(fixture.fixture_id, fixture.version) for fixture in self.fixtures]
        if len(fixture_keys) != len(set(fixture_keys)):
            raise ValueError("dataset contains duplicate fixture/version identities")

        fixture_keys_set = set(fixture_keys)
        for scenario in self.scenarios:
            missing = set(scenario.fixture_refs) - fixture_keys_set
            if missing:
                raise ValueError(
                    f"scenario {scenario.scenario_id} references unknown fixtures: {sorted(missing)}"
                )

    def fixture(self, fixture_id: str, version: str) -> BenchmarkEvidenceFixture:
        for fixture in self.fixtures:
            if (fixture.fixture_id, fixture.version) == (fixture_id, version):
                return fixture
        raise KeyError(f"unknown fixture version: {fixture_id!r}/{version!r}")

    def scenario(self, scenario_id: str, version: str) -> BenchmarkScenario:
        for scenario in self.scenarios:
            if (scenario.scenario_id, scenario.version) == (scenario_id, version):
                return scenario
        raise KeyError(f"unknown scenario version: {scenario_id!r}/{version!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "fixtures": [fixture.to_dict() for fixture in self.fixtures],
            "metadata": dict(self.metadata),
        }
