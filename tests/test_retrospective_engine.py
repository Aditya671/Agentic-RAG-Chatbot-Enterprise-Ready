from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    AgentObservability,
    Evidence,
    ExecutionEvent,
    ExecutionTrace,
    RetrospectiveEngine,
)


def test_retrospective_separates_facts_findings_and_recommendations():
    trace = ExecutionTrace()
    trace.add_event(
        ExecutionEvent(
            "retrieval.search",
            "retrieval",
            "success",
            trace.run_id,
            attributes={"result_count": 0},
        )
    )
    trace.finish("success")

    retrospective = RetrospectiveEngine().analyze(trace)

    assert retrospective.observed_facts
    assert retrospective.observed_facts[0].fact_id == "missing_evidence"
    assert retrospective.findings[0].category == "evidence"
    assert retrospective.findings[0].supporting_fact_ids == ("missing_evidence",)
    assert retrospective.recommendation_details[0].finding_ids == ("finding-1",)
    assert retrospective.recommendations[0].startswith("record source evidence")


def test_retrospective_identifies_retrieval_empty_results_and_failed_phase():
    trace = ExecutionTrace()
    trace.add_event(
        ExecutionEvent(
            "retrieval.search",
            "retrieval",
            "success",
            trace.run_id,
            attributes={"result_count": 0},
        )
    )
    trace.add_event(
        ExecutionEvent(
            "tool.search",
            "tool",
            "error",
            trace.run_id,
            attributes={"error_type": "TimeoutError"},
        )
    )
    trace.finish("error", "provider unavailable")

    retrospective = RetrospectiveEngine().analyze(trace)

    assert "provider unavailable" in retrospective.errors
    assert any(f.category == "execution" for f in retrospective.findings)
    assert any(f.category == "retrieval" for f in retrospective.findings)
    assert any(f.category == "execution" for f in retrospective.findings)
    assert any("retrieval filters" in r.action for r in retrospective.recommendation_details)


def test_retrospective_preserves_success_with_evidence_as_clean_run():
    observer = AgentObservability()
    with observer.run() as trace:
        observer.record_evidence(trace, Evidence("doc-1", "document"))
        observer.record_event(trace, name="agent.response", phase="response")

    retrospective = RetrospectiveEngine().analyze(trace)

    assert retrospective.findings == ()
    assert retrospective.recommendations == ()
    assert "no detected anomalies" in retrospective.observations[0]
