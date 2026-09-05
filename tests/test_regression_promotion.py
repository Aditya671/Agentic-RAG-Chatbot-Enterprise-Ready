from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    HarnessCase,
    RegressionPromotionEngine,
    Retrospective,
    RetrospectiveEngine,
    ScenarioCatalog,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.observability import AgentObservability


def _retrospective() -> Retrospective:
    observer = AgentObservability()
    with observer.run() as trace:
        observer.record_event(
            trace,
            name="retrieval.search",
            phase="retrieval",
            attributes={"result_count": 0},
        )
    return RetrospectiveEngine().analyze(trace)


def test_proposal_carries_retrospective_provenance() -> None:
    case = HarnessCase(case_id="retrieval-failure", question="What is the answer?")
    retrospective = _retrospective()

    proposal = RegressionPromotionEngine.propose(
        retrospective, case, proposal_id="proposal-1", finding_id="finding-1"
    )

    assert proposal.source_run_id == retrospective.run_id
    assert proposal.source_finding_id == "finding-1"
    assert proposal.source_fact_ids == ("retrieval_empty",)
    assert proposal.observation == retrospective.findings[0].summary
    assert proposal.case == case


def test_invalid_finding_cannot_be_promoted_as_if_it_were_current_provenance() -> None:
    case = HarnessCase(case_id="case-invalid", question="question")

    with pytest.raises(ValueError):
        RegressionPromotionEngine.propose(
            _retrospective(), case, proposal_id="proposal-invalid", finding_id="finding-999"
        )


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
    retrospective = _retrospective()
    proposal = RegressionPromotionEngine.propose(
        retrospective,
        case,
        proposal_id="proposal-3",
        finding_id="finding-1",
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
