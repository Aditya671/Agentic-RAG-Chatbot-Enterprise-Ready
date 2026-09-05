from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    BenchmarkConfig,
    BenchmarkDataset,
    BenchmarkEvidenceFixture,
    BenchmarkScenario,
    Claim,
    ClaimEvidenceLink,
    Evidence,
    EvidenceRecord,
    HarnessCase,
    ProvenanceRecord,
)


def _fixture() -> BenchmarkEvidenceFixture:
    evidence = Evidence(
        source_id="annual-report",
        source_type="document",
        excerpt="Revenue increased 12 percent.",
        relevance=0.95,
    )
    return BenchmarkEvidenceFixture(
        fixture_id="finance-baseline",
        version="1.0",
        evidence=(
            EvidenceRecord(
                evidence=evidence,
                provenance=ProvenanceRecord(record_id="prov-1"),
            ),
        ),
    )


def _scenario() -> BenchmarkScenario:
    return BenchmarkScenario(
        scenario_id="revenue-001",
        version="1.0",
        case=HarnessCase(
            case_id="revenue-001",
            question="Did revenue increase?",
            expected_text_contains=("increased",),
            expected_evidence_source_ids=("annual-report",),
        ),
        expected_capabilities=("retrieval", "grounding"),
        fixture_ids=("finance-baseline",),
        expected_claims=(
            Claim(
                claim_id="claim-1",
                text="Revenue increased.",
                required_evidence_source_ids=("annual-report",),
            ),
        ),
        expected_claim_evidence_links=(
            ClaimEvidenceLink(
                claim_id="claim-1",
                evidence_source_id="annual-report",
            ),
        ),
    )


def test_dataset_keeps_scenario_and_fixture_versions_isolated() -> None:
    dataset = BenchmarkDataset(
        dataset_id="agent-architecture",
        version="2026.09",
        scenarios=(_scenario(),),
        fixtures=(_fixture(),),
    )

    assert dataset.scenario("revenue-001", "1.0").fixture_ids == ("finance-baseline",)
    assert dataset.fixture("finance-baseline").version == "1.0"
    assert dataset.to_dict()["scenarios"][0]["expected_claims"][0]["claim_id"] == "claim-1"


def test_dataset_rejects_unknown_fixture_reference() -> None:
    scenario = _scenario()
    invalid = BenchmarkScenario(
        scenario_id=scenario.scenario_id,
        version=scenario.version,
        case=scenario.case,
        fixture_ids=("missing-fixture",),
    )

    with pytest.raises(ValueError, match="unknown fixtures"):
        BenchmarkDataset(
            dataset_id="agent-architecture",
            version="2026.09",
            scenarios=(invalid,),
            fixtures=(),
        )


def test_dataset_rejects_duplicate_scenario_versions() -> None:
    scenario = _scenario()
    with pytest.raises(ValueError, match="duplicate scenario/version"):
        BenchmarkDataset(
            dataset_id="agent-architecture",
            version="2026.09",
            scenarios=(scenario, scenario),
            fixtures=(_fixture(),),
        )


def test_benchmark_config_has_stable_identity() -> None:
    config = BenchmarkConfig(
        benchmark_id="architecture-comparison",
        version="1.0",
        scenario_set_version="2026.09",
        repetitions=3,
    )

    assert config.identity == "architecture-comparison@1.0::scenarios@2026.09"
    assert config.to_dict()["repetitions"] == 3


def test_benchmark_config_rejects_invalid_repetitions() -> None:
    with pytest.raises(ValueError, match="repetitions"):
        BenchmarkConfig(
            benchmark_id="architecture-comparison",
            version="1.0",
            scenario_set_version="2026.09",
            repetitions=0,
        )
