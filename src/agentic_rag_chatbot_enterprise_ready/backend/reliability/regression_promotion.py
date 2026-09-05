"""Governed promotion of retrospective findings into deterministic regressions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .contracts import utc_now
from .harness import HarnessCase, ScenarioCatalog
from .retrospective import Retrospective, RetrospectiveFinding


@dataclass(frozen=True, slots=True)
class RegressionProposal:
    """An auditable candidate derived from one retrospective finding."""

    proposal_id: str
    source_run_id: str
    observation: str
    recommendation: str
    case: HarnessCase
    created_at: datetime
    source_finding_id: str | None = None
    source_fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """Explicit human review decision for a regression proposal."""

    proposal_id: str
    reviewer: str
    approved: bool
    rationale: str
    reviewed_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewedRegression:
    """An approved scenario with its review and retrospective provenance attached."""

    proposal: RegressionProposal
    decision: ReviewDecision

    @property
    def case(self) -> HarnessCase:
        return self.proposal.case


class RegressionPromotionEngine:
    """Convert retrospective analysis into regressions only through explicit review."""

    @staticmethod
    def propose(
        retrospective: Retrospective,
        case: HarnessCase,
        *,
        proposal_id: str,
        observation: str | None = None,
        recommendation: str | None = None,
        finding_id: str | None = None,
    ) -> RegressionProposal:
        """Create a proposal while preserving the finding → fact provenance chain."""
        if not isinstance(retrospective, Retrospective):
            raise TypeError("retrospective must be a Retrospective")
        if not isinstance(case, HarnessCase):
            raise TypeError("case must be a HarnessCase")
        if not proposal_id.strip():
            raise ValueError("proposal_id must be non-empty")
        if not retrospective.run_id.strip():
            raise ValueError("retrospective.run_id must be non-empty")

        finding: RetrospectiveFinding | None = None
        if finding_id is not None:
            finding = next((item for item in retrospective.findings if item.finding_id == finding_id), None)
            if finding is None:
                raise ValueError("finding_id does not belong to the retrospective")
        elif retrospective.findings:
            finding = retrospective.findings[0]

        selected_observation = observation or (
            finding.summary if finding is not None else (retrospective.observations[0] if retrospective.observations else "")
        )
        selected_recommendation = recommendation or (
            next(
                (
                    item.action
                    for item in retrospective.recommendation_details
                    if finding is not None and finding.finding_id in item.finding_ids
                ),
                retrospective.recommendations[0] if retrospective.recommendations else "",
            )
        )
        if not selected_observation.strip():
            raise ValueError("proposal observation must be non-empty")
        if not selected_recommendation.strip():
            raise ValueError("proposal recommendation must be non-empty")

        return RegressionProposal(
            proposal_id=proposal_id,
            source_run_id=retrospective.run_id,
            observation=selected_observation,
            recommendation=selected_recommendation,
            case=case,
            created_at=utc_now(),
            source_finding_id=finding.finding_id if finding else None,
            source_fact_ids=finding.supporting_fact_ids if finding else (),
        )

    @staticmethod
    def review(
        proposal: RegressionProposal,
        *,
        reviewer: str,
        approved: bool,
        rationale: str,
    ) -> ReviewedRegression:
        """Record the explicit review decision; this does not promote the case."""
        if not isinstance(proposal, RegressionProposal):
            raise TypeError("proposal must be a RegressionProposal")
        if not reviewer.strip():
            raise ValueError("reviewer must be non-empty")
        if not rationale.strip():
            raise ValueError("rationale must be non-empty")
        decision = ReviewDecision(
            proposal_id=proposal.proposal_id,
            reviewer=reviewer,
            approved=approved,
            rationale=rationale,
            reviewed_at=utc_now(),
        )
        return ReviewedRegression(proposal=proposal, decision=decision)

    @staticmethod
    def promote(reviewed: ReviewedRegression, catalog: ScenarioCatalog) -> HarnessCase:
        """Add an approved reviewed scenario to the regression catalog."""
        if not isinstance(reviewed, ReviewedRegression):
            raise TypeError("reviewed must be a ReviewedRegression")
        if not isinstance(catalog, ScenarioCatalog):
            raise TypeError("catalog must be a ScenarioCatalog")
        if reviewed.decision.proposal_id != reviewed.proposal.proposal_id:
            raise ValueError("review decision does not match proposal")
        if not reviewed.decision.approved:
            raise PermissionError("regression proposal was not approved")
        catalog.add(reviewed.case)
        return reviewed.case
