"""Reviewed promotion of retrospective findings into deterministic regression cases."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .contracts import utc_now
from .harness import HarnessCase, ScenarioCatalog
from .retrospective import Retrospective


@dataclass(frozen=True, slots=True)
class RegressionProposal:
    """An auditable candidate derived from a recorded retrospective."""

    proposal_id: str
    source_run_id: str
    observation: str
    recommendation: str
    case: HarnessCase
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """Human review decision for a regression proposal."""

    proposal_id: str
    reviewer: str
    approved: bool
    rationale: str
    reviewed_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewedRegression:
    """An approved scenario with its review provenance attached."""

    proposal: RegressionProposal
    decision: ReviewDecision

    @property
    def case(self) -> HarnessCase:
        return self.proposal.case


class RegressionPromotionEngine:
    """Convert retrospective facts into scenarios only after explicit review."""

    @staticmethod
    def propose(
        retrospective: Retrospective,
        case: HarnessCase,
        *,
        proposal_id: str,
        observation: str | None = None,
        recommendation: str | None = None,
    ) -> RegressionProposal:
        if not isinstance(retrospective, Retrospective):
            raise TypeError("retrospective must be a Retrospective")
        if not isinstance(case, HarnessCase):
            raise TypeError("case must be a HarnessCase")
        if not proposal_id.strip():
            raise ValueError("proposal_id must be non-empty")
        if not retrospective.run_id.strip():
            raise ValueError("retrospective.run_id must be non-empty")
        selected_observation = observation or (retrospective.observations[0] if retrospective.observations else "")
        selected_recommendation = recommendation or (
            retrospective.recommendations[0] if retrospective.recommendations else ""
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
        )

    @staticmethod
    def review(
        proposal: RegressionProposal,
        *,
        reviewer: str,
        approved: bool,
        rationale: str,
    ) -> ReviewedRegression:
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
