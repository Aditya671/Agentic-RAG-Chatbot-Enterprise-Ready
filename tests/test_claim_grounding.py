from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    Claim,
    ClaimEvidenceLink,
    ClaimGroundingEvaluator,
    Evidence,
    EvidenceRecord,
    ProvenanceRecord,
)


def _evidence(*source_ids: str) -> tuple[EvidenceRecord, ...]:
    return tuple(
        EvidenceRecord(
            Evidence(source_id=source_id, source_type="document", relevance=0.9),
            ProvenanceRecord(record_id=f"prov-{source_id}"),
        )
        for source_id in source_ids
    )


def test_claim_is_supported_when_required_evidence_is_explicitly_linked() -> None:
    claims = (Claim("claim-1", "Revenue increased.", ("doc-a",)),)
    links = (ClaimEvidenceLink("claim-1", "doc-a"),)

    result = ClaimGroundingEvaluator.evaluate(claims, links, _evidence("doc-a"))

    assert result.passed is True
    assert result.claim_coverage == 1.0
    assert result.supported_claims == 1


def test_missing_required_evidence_fails_grounding() -> None:
    claims = (Claim("claim-1", "Revenue increased.", ("doc-a", "doc-b")),)
    links = (ClaimEvidenceLink("claim-1", "doc-a"),)

    result = ClaimGroundingEvaluator.evaluate(claims, links, _evidence("doc-a"))

    assert result.passed is False
    assert result.claim_coverage == 0.0
    assert "doc-b" in result.failures[0]


def test_contradictory_evidence_is_an_explicit_failure() -> None:
    claims = (Claim("claim-1", "Revenue increased."),)
    links = (
        ClaimEvidenceLink("claim-1", "doc-a", "supports"),
        ClaimEvidenceLink("claim-1", "doc-b", "contradicts"),
    )

    result = ClaimGroundingEvaluator.evaluate(claims, links, _evidence("doc-a", "doc-b"))

    assert result.passed is False
    assert result.claim_coverage == 0.0
    assert "contradictory evidence" in result.failures[0]


def test_unavailable_linked_evidence_is_reported() -> None:
    claims = (Claim("claim-1", "Revenue increased."),)
    links = (ClaimEvidenceLink("claim-1", "missing-doc"),)

    result = ClaimGroundingEvaluator.evaluate(claims, links, _evidence("doc-a"))

    assert result.passed is False
    assert any("unavailable evidence" in failure for failure in result.failures)


def test_unknown_claim_reference_is_rejected() -> None:
    claims = (Claim("claim-1", "Revenue increased."),)
    links = (ClaimEvidenceLink("unknown", "doc-a"),)

    with pytest.raises(ValueError, match="unknown claim"):
        ClaimGroundingEvaluator.evaluate(claims, links, _evidence("doc-a"))


def test_empty_claim_set_is_zero_work_and_full_coverage() -> None:
    result = ClaimGroundingEvaluator.evaluate((), (), ())

    assert result.passed is True
    assert result.claim_coverage == 1.0
    assert result.supported_claims == 0
    assert result.total_claims == 0
