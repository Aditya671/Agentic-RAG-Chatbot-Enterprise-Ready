"""Explicit claim-to-evidence relationships for deterministic grounding evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import EvidenceRecord

_ALLOWED_RELATIONSHIPS = {"supports", "contradicts", "contextual"}


@dataclass(frozen=True, slots=True)
class Claim:
    """A response claim whose grounding requirements are explicit and auditable."""

    claim_id: str
    text: str
    required_evidence_source_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.text.strip():
            raise ValueError("claim_id and text must be non-empty")
        if any(not source_id.strip() for source_id in self.required_evidence_source_ids):
            raise ValueError("required evidence source IDs must be non-empty")


@dataclass(frozen=True, slots=True)
class ClaimEvidenceLink:
    """An explicit relationship between one claim and one evidence source."""

    claim_id: str
    evidence_source_id: str
    relationship: str = "supports"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.evidence_source_id.strip():
            raise ValueError("claim_id and evidence_source_id must be non-empty")
        if self.relationship not in _ALLOWED_RELATIONSHIPS:
            raise ValueError("relationship must be supports, contradicts, or contextual")


@dataclass(frozen=True, slots=True)
class GroundingResult:
    """Deterministic claim-grounding measurements."""

    passed: bool
    claim_coverage: float
    supported_claims: int
    total_claims: int
    failures: tuple[str, ...] = ()


class ClaimGroundingEvaluator:
    """Evaluate explicit claim/evidence links without an LLM or semantic judge."""

    @staticmethod
    def evaluate(
        claims: tuple[Claim, ...],
        links: tuple[ClaimEvidenceLink, ...],
        evidence: tuple[EvidenceRecord, ...],
    ) -> GroundingResult:
        if not isinstance(claims, tuple) or not all(isinstance(c, Claim) for c in claims):
            raise TypeError("claims must be a tuple of Claim instances")
        if not isinstance(links, tuple) or not all(isinstance(link, ClaimEvidenceLink) for link in links):
            raise TypeError("links must be a tuple of ClaimEvidenceLink instances")
        if not isinstance(evidence, tuple) or not all(isinstance(e, EvidenceRecord) for e in evidence):
            raise TypeError("evidence must be a tuple of EvidenceRecord instances")

        evidence_ids = {record.evidence.source_id for record in evidence}
        claim_ids = {claim.claim_id for claim in claims}
        links_by_claim: dict[str, set[str]] = {}
        contradictions_by_claim: dict[str, set[str]] = {}
        failures: list[str] = []

        for link in links:
            if link.claim_id not in claim_ids:
                raise ValueError(f"link references unknown claim: {link.claim_id}")
            if link.evidence_source_id not in evidence_ids:
                failures.append(
                    f"claim {link.claim_id} references unavailable evidence "
                    f"{link.evidence_source_id}"
                )
                continue
            if link.relationship == "supports":
                links_by_claim.setdefault(link.claim_id, set()).add(link.evidence_source_id)
            elif link.relationship == "contradicts":
                contradictions_by_claim.setdefault(link.claim_id, set()).add(link.evidence_source_id)

        supported = 0
        for claim in claims:
            required = set(claim.required_evidence_source_ids)
            support = links_by_claim.get(claim.claim_id, set())
            contradictions = contradictions_by_claim.get(claim.claim_id, set())
            missing_required = required - support

            if missing_required:
                failures.append(
                    f"claim {claim.claim_id} is missing required evidence: "
                    f"{sorted(missing_required)}"
                )
                continue
            if not required and not support:
                failures.append(f"claim {claim.claim_id} has no supporting evidence link")
                continue
            if contradictions:
                failures.append(
                    f"claim {claim.claim_id} has explicit contradictory evidence: "
                    f"{sorted(contradictions)}"
                )
                continue
            supported += 1

        total = len(claims)
        coverage = supported / total if total else 1.0
        return GroundingResult(
            passed=not failures,
            claim_coverage=coverage,
            supported_claims=supported,
            total_claims=total,
            failures=tuple(failures),
        )
