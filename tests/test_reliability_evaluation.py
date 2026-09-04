from datetime import datetime, timezone

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    Evidence,
    EvaluationEngine,
    ExecutionTrace,
)


def _trace(outcome: str, evidence: bool = False) -> ExecutionTrace:
    trace = ExecutionTrace()
    if evidence:
        trace.add_evidence(
            __import__("agentic_rag_chatbot_enterprise_ready.backend.reliability", fromlist=["EvidenceRecord"]).EvidenceRecord(
                Evidence("doc-1", "document", "page:1"),
                __import__("agentic_rag_chatbot_enterprise_ready.backend.reliability", fromlist=["ProvenanceRecord"]).ProvenanceRecord(
                    "prov-1", operation="retrieval"
                ),
            )
        )
    trace.finish(outcome)
    return trace


def test_evaluation_aggregates_success_evidence_and_errors():
    result = EvaluationEngine.evaluate([_trace("success", True), _trace("error")])
    assert result.total_runs == 2
    assert result.successful_runs == 1
    assert result.failed_runs == 1
    assert result.success_rate == 0.5
    assert result.evidence_coverage == 0.5
    assert result.error_rate == 0.5


def test_evaluation_empty_collection_is_zero_safe():
    result = EvaluationEngine.evaluate([])
    assert result.total_runs == 0
    assert result.success_rate == 0.0
    assert result.evidence_coverage == 0.0
    assert result.average_latency_ms == 0.0


def test_evaluation_rejects_non_traces():
    with pytest.raises(TypeError):
        EvaluationEngine.evaluate([object()])


def test_duration_is_computed_from_trace_timestamps():
    trace = ExecutionTrace()
    trace.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    trace.finished_at = datetime(2026, 1, 1, 0, 0, 1, 500000, tzinfo=timezone.utc).isoformat()
    trace.outcome = "success"
    result = EvaluationEngine.evaluate([trace])
    assert result.average_latency_ms == 1500.0
