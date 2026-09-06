from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import ApplicationRequest, Capability
from agentic_rag_chatbot_enterprise_ready.backend.application_runtime_adapter import build_application_runtime


class FakeAgentSystem:
    async def get_response(self, question: str):
        assert question == "What is the policy?"
        return {
            "response_text": "The policy is documented.",
            "response_metadata": [{"id": "doc-1", "type": "document", "page": 2, "score": 0.91, "provider": "fixture", "content": "sensitive body omitted"}],
        }

    async def upload_and_index_files_async(self, uploaded_files):
        assert uploaded_files[0]["name"] == "a.txt"
        return self.upload_result

    def check_indexing_status(self, task_id):
        return f"Task {task_id} completed successfully."

    upload_result = "task-1"


@pytest.mark.asyncio
async def test_maintained_question_path_uses_canonical_application_contract() -> None:
    runtime = build_application_runtime(FakeAgentSystem())
    execution = await runtime.execute(ApplicationRequest(question="  What   is the policy?  ", session_id="s-1"))
    evidence = execution.result.evidence[0]
    assert execution.result.capability is Capability.QUESTION
    assert execution.result.response_text == "The policy is documented."
    assert evidence.source_id == "doc-1"
    assert evidence.source_type == "document"
    assert evidence.locator == "2"
    assert evidence.relevance == 0.91
    assert evidence.metadata["provider"] == "fixture"
    assert len(execution.trace.evidence) == 1
    assert execution.trace.session_id == "s-1"


@pytest.mark.asyncio
async def test_upload_and_status_are_explicit_capabilities() -> None:
    runtime = build_application_runtime(FakeAgentSystem())
    upload = await runtime.execute(ApplicationRequest(capability=Capability.UPLOAD, payload={"uploaded_files": [{"name": "a.txt", "content": b"hello"}]}))
    status = await runtime.execute(ApplicationRequest(capability=Capability.INDEX_STATUS, payload={"task_id": "task-1"}))
    assert upload.result.response_text == "Document indexing task submitted: task-1"
    assert upload.result.metadata["task_id"] == "task-1"
    assert status.result.response_text == "Task task-1 completed successfully."
    assert status.result.metadata["task_id"] == "task-1"


@pytest.mark.asyncio
async def test_legacy_upload_response_is_normalized_to_task_id() -> None:
    system = FakeAgentSystem()
    system.upload_result = (
        "File indexing has been started in the background. Your Task ID is: "
        "celery-task-123. Use the 'check_indexing_status' tool to check progress."
    )
    runtime = build_application_runtime(system)
    upload = await runtime.execute(
        ApplicationRequest(
            capability=Capability.UPLOAD,
            payload={"uploaded_files": [{"name": "a.txt", "content": b"hello"}]},
        )
    )
    assert upload.result.metadata["task_id"] == "celery-task-123"
    assert upload.result.response_text == "Document indexing task submitted: celery-task-123"


@pytest.mark.asyncio
async def test_retrieval_body_is_not_copied_into_evidence_metadata() -> None:
    runtime = build_application_runtime(FakeAgentSystem())
    execution = await runtime.execute(ApplicationRequest(question="What is the policy?"))
    assert "content" not in execution.result.evidence[0].metadata
