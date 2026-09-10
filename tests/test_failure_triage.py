from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    FailureTriageEngine,
    FailureClass,
    RetrospectiveEngine,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.contracts import ExecutionTrace


def _error_retrospective():
    trace = ExecutionTrace(run_id="run-1", session_id="session-1", actor_id="actor-1")
    trace.outcome = "error"
    trace.error = "provider unavailable"
    return RetrospectiveEngine().analyze(trace)


def test_failure_triage_promotes_high_execution_failure_to_critical():
    triage = FailureTriageEngine().analyze(_error_retrospective())
    assert triage.priority.value == "critical"
    assert triage.requires_operator is True
    assert triage.items[0].category == "execution"
    assert triage.items[0].priority.value == "critical"


def test_failure_triage_reuses_existing_retrospective_findings():
    retrospective = _error_retrospective()
    triage = FailureTriageEngine().analyze(retrospective)
    assert triage.items[0].finding_ids == (retrospective.findings[0].finding_id,)
    assert triage.items[0].summary == retrospective.findings[0].summary


def test_failure_triage_has_no_identity_or_error_payload_fields():
    triage = FailureTriageEngine().analyze(_error_retrospective())
    payload = repr(triage)
    assert "actor-1" not in payload
    assert "session-1" not in payload
    assert "provider unavailable" not in payload


def test_failure_triage_empty_success_is_low_priority():
    trace = ExecutionTrace(run_id="run-2")
    trace.outcome = "success"
    retrospective = RetrospectiveEngine().analyze(trace)
    triage = FailureTriageEngine().analyze(retrospective)
    assert triage.priority.value == "medium"
    assert triage.requires_operator is False


def test_failure_classification_contract_remains_available():
    assert FailureClass.TERMINAL.value == "terminal"
