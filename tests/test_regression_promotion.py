from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    HarnessCase,
    RegressionPromotionEngine,
    Retrospective,
    ScenarioCatalog,
)


def _retrospective() -> Retrospective:
    return Retrospective(
        run_id="run-123",
        outcome="failure",
        event_count=3,
        evidence_count=0,
        errors=("retrieval failed",),
        observations=("execution contained one or more errors",),
        recommendations=("inspect the failing execution phase and provider boundary",),
    )


def test_proposal_carries_retrospective_provenance() -> None:
    case = HarnessCase(case_id="retrieval-failure", question="What is the answer?")

    proposal = RegressionPromotionEngine.propose(
        _retrospective(), case, proposal_id="proposal-1"
    )

    assert proposal.source_run_id == "run-123"
    assert proposal.observation == "execution contained one or more errors"
    assert proposal.recommendation == "inspect the failing execution phase and provider boundary"
    assert proposal.case == case


def test_unapproved_proposal_cannot_enter_catalog() -> None:
    case = HarnessCase(case_id="case-a", question="question")
    proposal = RegressionPromotionEngine.propose(
        _retrospective(), case, proposal_id="proposal-2"
    )
    reviewed = RegressionPromotionEngine.review(
        proposal,
        reviewer="reviewer@example",
        approved=False,
        rationale="The failure was caused by an external outage and is not a stable regression.",
    )
    catalog = ScenarioCatalog()

    with pytest.raises(PermissionError):
        RegressionPromotionEngine.promote(reviewed, catalog)

    assert catalog.cases() == ()


def test_approved_review_promotes_exact_case() -> None:
    case = HarnessCase(
        case_id="case-b",
        question="Which source supports the answer?",
        expected_evidence_source_ids=("doc-1",),
    )
    proposal = RegressionPromotionEngine.propose(
        _retrospective(),
        case,
        proposal_id="proposal-3",
        observation="retrieval produced no evidence",
        recommendation="require evidence before accepting the answer",
    )
    reviewed = RegressionPromotionEngine.review(
        proposal,
        reviewer="reviewer@example",
        approved=True,
        rationale="This is a reproducible reliability gap worth protecting with a regression case.",
    )
    catalog = ScenarioCatalog()

    promoted = RegressionPromotionEngine.promote(reviewed, catalog)

    assert promoted == case
    assert catalog.get("case-b") == case


def test_review_must_match_proposal_and_require_auditable_fields() -> None:
    case = HarnessCase(case_id="case-c", question="question")
    proposal = RegressionPromotionEngine.propose(
        _retrospective(), case, proposal_id="proposal-4"
    )

    with pytest.raises(ValueError):
        RegressionPromotionEngine.review(proposal, reviewer="", approved=True, rationale="ok")
    with pytest.raises(ValueError):
        RegressionPromotionEngine.review(proposal, reviewer="reviewer", approved=True, rationale="")

    reviewed = RegressionPromotionEngine.review(
        proposal,
        reviewer="reviewer",
        approved=True,
        rationale="approved after reproduction",
    )
    assert reviewed.decision.proposal_id == proposal.proposal_id
