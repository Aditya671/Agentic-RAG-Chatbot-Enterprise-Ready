from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    AgentObservability, Evidence, HarnessCase, HarnessEngine, InMemoryReliabilityStore,
    MonitoringEngine, RetrospectiveEngine,
)


async def test_observability_records_phase_and_evidence():
    observer = AgentObservability()
    with observer.run(attributes={"model": "test"}) as trace:
        with observer.phase(trace, "retrieval", "retrieval"):
            observer.record_evidence(trace, Evidence("doc-1", "document", "page:2"), provider="fake")
    assert trace.outcome == "success"
    assert len(trace.evidence) == 1
    assert trace.evidence[0].provenance.provider == "fake"
    assert observer.store.get(trace.run_id) is trace


async def test_harness_passes_and_persists_trace():
    store = InMemoryReliabilityStore()
    harness = HarnessEngine(store)
    result = await harness.run_case(
        HarnessCase("greeting", "hello", expected_text_contains=("hello",)),
        lambda question: _answer(question),
    )
    assert result.passed is True
    assert store.get(result.run_id) is not None


async def test_harness_captures_assertion_failure():
    harness = HarnessEngine()
    result = await harness.run_case(
        HarnessCase("grounding", "question", expected_text_contains=("evidence",)),
        lambda question: _answer("unsupported answer"),
    )
    assert result.passed is False
    assert result.outcome == "assertion_failed"


async def test_harness_accepts_expected_error():
    harness = HarnessEngine()

    async def fail(question):
        raise RuntimeError("provider unavailable")

    result = await harness.run_case(HarnessCase("outage", "question", expected_outcome="error"), fail)
    assert result.passed is True


def test_retrospective_and_monitoring_are_explainable():
    observer = AgentObservability()
    with observer.run() as trace:
        observer.record_evidence(trace, Evidence("doc-1", "document"))
    retrospective = RetrospectiveEngine().analyze(trace)
    assert "recorded evidence" in retrospective.observations[0]
    health = MonitoringEngine().snapshot([trace])
    assert health.total_runs == 1
    assert health.error_rate == 0.0
    assert health.evidence_coverage == 1.0


async def _answer(question):
    return {"response_text": f"hello: {question}"}
