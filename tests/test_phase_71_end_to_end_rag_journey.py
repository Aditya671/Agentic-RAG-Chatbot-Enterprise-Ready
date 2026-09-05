from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import (
    ApplicationRequest,
    Capability,
)
from agentic_rag_chatbot_enterprise_ready.backend.application_runtime_adapter import (
    build_application_runtime,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    Evidence,
    HarnessCase,
    HarnessEngine,
    ScenarioCatalog,
)


POLICY = {"name": "approval-policy.pdf", "content": b"All capital approvals require documented approval."}
QUESTION = "What does the approval policy require?"


class FakeIndexer:
    """Deterministic stand-in for the maintained upload/index implementation."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []
        self.indexed: list[str] = []

    async def index_uploaded_files(self, file_list):
        self.calls.append(list(file_list))
        self.indexed = [str(item["name"]) for item in file_list]
        return {
            "indexed": self.indexed,
            "skipped": [],
            "chunks": 1,
            "status": "completed",
        }


class FakeEndToEndSystem:
    """Joins fake ingestion and retrieval while preserving real application boundaries."""

    def __init__(self, indexer: FakeIndexer) -> None:
        self.local_file_indexer = indexer
        self.indexer = indexer

    def check_indexing_status(self, task_id):
        return f"Task {task_id} completed successfully."

    async def get_response(self, question: str):
        assert self.indexer.indexed == [POLICY["name"]]
        return {
            "response_text": "The approval policy requires documented approval for capital approvals.",
            "response_metadata": {
                "sources": [
                    {
                        "id": POLICY["name"],
                        "type": "uploaded_document",
                        "page": 1,
                        "score": 0.97,
                        "content": POLICY["content"].decode(),
                    }
                ]
            },
        }


@pytest.mark.asyncio
async def test_phase_71_proves_upload_index_retrieve_grounded_answer_journey() -> None:
    indexer = FakeIndexer()
    system = FakeEndToEndSystem(indexer)
    runtime = build_application_runtime(system)

    upload = await runtime.execute(
        ApplicationRequest(
            capability=Capability.UPLOAD,
            payload={"uploaded_files": [POLICY]},
            session_id="phase-71",
            actor_id="scenario-fixture",
        )
    )
    assert upload.result.response_text == "Document ingestion completed: 1 indexed, 0 unchanged."
    assert indexer.calls == [[POLICY]]

    question = await runtime.execute(
        ApplicationRequest(
            capability=Capability.QUESTION,
            question=f"  {QUESTION}  ",
            session_id="phase-71",
            actor_id="scenario-fixture",
        )
    )

    assert question.result.response_text.startswith("The approval policy requires documented approval")
    assert question.result.evidence == (
        Evidence(
            source_id=POLICY["name"],
            source_type="uploaded_document",
            locator="1",
            relevance=0.97,
            metadata={
                "id": POLICY["name"],
                "type": "uploaded_document",
                "page": 1,
                "score": 0.97,
            },
        ),
    )
    assert "content" not in question.result.evidence[0].metadata
    assert len(question.trace.evidence) == 1
    assert question.trace.evidence[0].provenance.operation == "application.retrieve"
    assert any(event.name == "capability.selected" for event in question.trace.events)
    assert any(event.name == "response.emitted" for event in question.trace.events)


@pytest.mark.asyncio
async def test_phase_71_turns_the_journey_into_a_replayable_benchmark_case() -> None:
    indexer = FakeIndexer()
    system = FakeEndToEndSystem(indexer)
    runtime = build_application_runtime(system)

    catalog = ScenarioCatalog(
        [
            HarnessCase(
                case_id="phase-71-uploaded-policy-grounded-answer",
                question=QUESTION,
                expected_text_contains=("documented approval",),
                expected_evidence_source_ids=(POLICY["name"],),
                min_evidence_relevance=0.9,
                metadata={
                    "phase": 71,
                    "fixture": "approval-policy.pdf",
                    "journey": "upload-index-retrieve-answer",
                },
            )
        ]
    )

    async def execute(question: str):
        if not indexer.indexed:
            await runtime.execute(
                ApplicationRequest(
                    capability=Capability.UPLOAD,
                    payload={"uploaded_files": [POLICY]},
                    session_id="phase-71-replay",
                    actor_id="scenario-fixture",
                )
            )
        execution = await runtime.execute(
            ApplicationRequest(
                capability=Capability.QUESTION,
                question=question,
                session_id="phase-71-replay",
                actor_id="scenario-fixture",
            )
        )
        return {
            "response_text": execution.result.response_text,
            "evidence": execution.result.evidence,
        }

    result = await HarnessEngine().replay(
        "phase-71-uploaded-policy-grounded-answer",
        catalog,
        execute,
    )

    assert result.passed is True
    assert result.grounding_coverage == 1.0
    assert result.retrieval_relevance == 0.97
