from agentic_rag_chatbot_enterprise_ready.backend.reliability import Evidence, ExecutionTrace
from agentic_rag_chatbot_enterprise_ready.backend.reliability.durable_store import JsonlReliabilityStore


def test_jsonl_store_survives_reload(tmp_path):
    path = tmp_path / "traces.jsonl"
    store = JsonlReliabilityStore(path)
    trace = ExecutionTrace()
    trace.add_evidence(
        __import__("agentic_rag_chatbot_enterprise_ready.backend.reliability", fromlist=["EvidenceRecord"]).EvidenceRecord(
            Evidence("doc-1", "document", "page:3"),
            __import__("agentic_rag_chatbot_enterprise_ready.backend.reliability", fromlist=["ProvenanceRecord"]).ProvenanceRecord(
                "prov-1", operation="retrieval", provider="test"
            ),
        )
    )
    trace.finish("success")
    store.save(trace)

    reloaded = JsonlReliabilityStore(path)
    recovered = reloaded.get(trace.run_id)
    assert recovered is not None
    assert recovered.outcome == "success"
    assert recovered.evidence[0].evidence.locator == "page:3"
    assert recovered.evidence[0].provenance.provider == "test"


def test_jsonl_store_latest_record_wins(tmp_path):
    path = tmp_path / "traces.jsonl"
    store = JsonlReliabilityStore(path)
    trace = ExecutionTrace()
    trace.finish("success")
    store.save(trace)
    trace.finish("error", "changed")
    store.save(trace)

    reloaded = JsonlReliabilityStore(path)
    assert reloaded.get(trace.run_id).outcome == "error"
    assert reloaded.get(trace.run_id).error == "changed"
    assert len(reloaded.recent()) == 1
