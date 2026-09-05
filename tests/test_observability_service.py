from __future__ import annotations

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    AgentObservability,
    Evidence,
    ExecutionTrace,
    InMemoryReliabilityStore,
    ObservabilityService,
    TraceQuery,
)


def test_run_has_stable_correlation_identifiers_and_lifecycle_metadata():
    store = InMemoryReliabilityStore()
    observer = AgentObservability(store)
    with observer.run(request_id="req-1", session_id="sess-1", actor_id="opaque-user-1") as trace:
        observer.record_event(trace, name="agent.plan", phase="decision", attributes={"strategy": "retrieval_first"})
        observer.record_tool_call(trace, tool="search", arguments_hash="hash-1", result_summary="2 results")
        observer.record_retrieval(trace, (Evidence("doc-1", "document", relevance=0.9),), provider="fake")
        observer.record_model_call(trace, provider="test", model="model-1", input_tokens=10, output_tokens=5)
        observer.record_response(trace, response_hash="response-hash", response_length=42)

    stored = store.get(trace.run_id)
    assert stored is trace
    assert trace.request_id == "req-1"
    assert trace.session_id == "sess-1"
    assert trace.actor_id == "opaque-user-1"
    assert {event.phase for event in trace.events} >= {"execution", "decision", "tool", "retrieval", "model", "response"}
    assert trace.evidence[0].provenance.record_id == "prov-doc-1-1"


def test_service_inspects_run_without_reconstructing_raw_logs():
    store = InMemoryReliabilityStore()
    trace = ExecutionTrace(request_id="req-2", session_id="sess-2", actor_id="opaque-user-2")
    observer = AgentObservability(store)
    observer.record_event(trace, name="agent.plan", phase="decision")
    observer.record_tool_call(trace, tool="search")
    observer.record_retrieval(trace, (Evidence("doc-2", "document"),))
    observer.record_model_call(trace, provider="test", model="model-1")
    observer.record_response(trace, response_hash="response-hash")
    trace.finish("success")
    store.save(trace)

    inspection = ObservabilityService(store).get_run(trace.run_id)
    assert inspection is not None
    assert inspection.tool_calls == 1
    assert inspection.model_calls == 1
    assert inspection.retrieval_calls == 1
    assert inspection.provenance_ids == ("prov-doc-2-1",)
    assert inspection.trace.run_id == trace.run_id


def test_service_filters_correlated_runs_and_reports_health():
    store = InMemoryReliabilityStore()
    for request_id, outcome, session_id in (("req-a", "success", "sess-a"), ("req-b", "error", "sess-b")):
        trace = ExecutionTrace(request_id=request_id, session_id=session_id)
        trace.finish(outcome, "provider failed" if outcome == "error" else None)
        store.save(trace)

    service = ObservabilityService(store)
    matches = service.search(TraceQuery(session_id="sess-b"))
    assert len(matches) == 1
    assert matches[0].trace.request_id == "req-b"

    health = service.health()
    assert health.total_runs == 2
    assert health.failed_runs == 1
    assert health.error_rate == 0.5


def test_query_limit_is_validated():
    store = InMemoryReliabilityStore()
    service = ObservabilityService(store)
    try:
        service.search(TraceQuery(limit=0))
    except ValueError as exc:
        assert "positive integer" in str(exc)
    else:
        raise AssertionError("expected ValueError")
