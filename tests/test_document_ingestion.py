from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import ApplicationRequest, Capability
from agentic_rag_chatbot_enterprise_ready.backend.application_runtime_adapter import build_application_runtime
from agentic_rag_chatbot_enterprise_ready.backend.reliability import DocumentIngestionService


class FakeIndexer:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def index_uploaded_files(self, file_list):
        self.calls.append(list(file_list))
        return self.result


@pytest.mark.asyncio
async def test_ingestion_delegates_to_maintained_indexer_and_normalizes_outcome() -> None:
    indexer = FakeIndexer({"indexed": ["policy.pdf"], "skipped": ["old.txt"], "chunks": 14, "status": "completed"})
    service = DocumentIngestionService(indexer)

    result = await service.ingest([{"name": "policy.pdf", "content": b"policy"}])

    assert len(indexer.calls) == 1
    assert result.artifacts[0].filename == "policy.pdf"
    assert result.artifacts[0].status == "indexed"
    assert result.artifacts[0].chunks == 14
    assert result.artifacts[1].status == "skipped"
    assert result.accepted == result.artifacts
    assert result.failed == ()


@pytest.mark.asyncio
async def test_empty_upload_batch_is_rejected_before_indexer_call() -> None:
    indexer = FakeIndexer({"indexed": []})
    service = DocumentIngestionService(indexer)

    with pytest.raises(ValueError, match="non-empty"):
        await service.ingest([])
    assert indexer.calls == []


@pytest.mark.asyncio
async def test_malformed_indexer_result_is_visible_as_contract_failure() -> None:
    indexer = FakeIndexer("completed")
    service = DocumentIngestionService(indexer)

    with pytest.raises(TypeError, match="mapping"):
        await service.ingest([{"name": "policy.pdf", "content": b"policy"}])


@pytest.mark.asyncio
async def test_failed_artifact_is_not_reported_as_success() -> None:
    indexer = FakeIndexer({"failed": {"policy.pdf": "unsupported type"}, "status": "completed"})
    service = DocumentIngestionService(indexer)

    result = await service.ingest([{"name": "policy.pdf", "content": b"policy"}])

    assert len(result.failed) == 1
    assert result.failed[0].reason == "unsupported type"
    assert result.accepted == ()


class FakeSystem:
    def __init__(self, indexer):
        self.local_file_indexer = indexer

    def check_indexing_status(self, task_id):
        return f"Task {task_id} completed successfully."

    async def get_response(self, question):
        return {"response_text": "Grounded answer.", "response_metadata": []}


@pytest.mark.asyncio
async def test_application_upload_uses_ingestion_contract() -> None:
    indexer = FakeIndexer({"indexed": ["policy.pdf"], "skipped": [], "chunks": 8, "status": "completed"})
    runtime = build_application_runtime(FakeSystem(indexer))

    execution = await runtime.execute(
        ApplicationRequest(
            capability=Capability.UPLOAD,
            payload={"uploaded_files": [{"name": "policy.pdf", "content": b"policy"}]},
        )
    )

    assert execution.result.capability is Capability.UPLOAD
    assert execution.result.response_text == "Document ingestion completed: 1 indexed, 0 unchanged."
    assert execution.result.metadata["chunks"] == 8
    assert len(indexer.calls) == 1


@pytest.mark.asyncio
async def test_application_upload_surfaces_failed_artifacts() -> None:
    indexer = FakeIndexer({"failed": {"policy.pdf": "unsupported type"}, "status": "completed"})
    runtime = build_application_runtime(FakeSystem(indexer))

    with pytest.raises(RuntimeError, match="failed for 1 artifact"):
        await runtime.execute(
            ApplicationRequest(
                capability=Capability.UPLOAD,
                payload={"uploaded_files": [{"name": "policy.pdf", "content": b"policy"}]},
            )
        )
