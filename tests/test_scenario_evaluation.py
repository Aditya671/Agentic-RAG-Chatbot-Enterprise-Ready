from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    Evidence,
    HarnessCase,
    HarnessEngine,
    ScenarioEvaluationEngine,
    ExecutionTrace,
)


async def _answer(question):
    return {
        "response_text": f"answer for {question}",
        "evidence": [
            Evidence("doc-a", "document", "page:1", relevance=0.9),
            Evidence("doc-b", "document", "page:2", relevance=0.8),
        ],
    }


def test_scenario_evaluation_measures_expected_evidence_and_relevance():
    trace = ExecutionTrace()
    trace.add_evidence(__import__(
        "agentic_rag_chatbot_enterprise_ready.backend.reliability",
        fromlist=["EvidenceRecord", "ProvenanceRecord"],
    ).EvidenceRecord(
        Evidence("doc-a", "document", "page:1", relevance=0.9),
        __import__(
            "agentic_rag_chatbot_enterprise_ready.backend.reliability",
            fromlist=["ProvenanceRecord"],
        ).ProvenanceRecord("prov-a", operation="retrieval"),
    ))
    case = HarnessCase(
        "grounded",
        "question",
        expected_text_contains=("answer",),
        expected_evidence_source_ids=("doc-a", "doc-b"),
        min_evidence_relevance=0.8,
    )
    result = ScenarioEvaluationEngine.evaluate(case, trace, "answer")
    assert result.passed is False
    assert result.grounding_coverage == 0.5
    assert result.retrieval_relevance == 0.9
    assert "doc-b" in result.failures[1]


async def test_harness_records_executor_evidence_and_reports_metrics():
    harness = HarnessEngine()
    result = await harness.run_case(
        HarnessCase(
            "grounded",
            "question",
            expected_text_contains=("answer",),
            expected_evidence_source_ids=("doc-a", "doc-b"),
            min_evidence_relevance=0.8,
        ),
        _answer,
    )
    assert result.passed is True
    assert result.grounding_coverage == 1.0
    assert result.retrieval_relevance == 0.85


async def test_harness_fails_when_retrieval_relevance_is_below_threshold():
    async def weak_answer(question):
        return {"response_text": "answer", "evidence": [Evidence("doc-a", "document", relevance=0.4)]}

    result = await HarnessEngine().run_case(
        HarnessCase("weak", "question", min_evidence_relevance=0.8),
        weak_answer,
    )
    assert result.passed is False
    assert "relevance below" in result.failures[0]
