"""Adapters from maintained implementations into the application boundary."""
from __future__ import annotations

from typing import Any

from .application_runtime import ApplicationRequest, ApplicationRuntime, Capability
from .reliability import DocumentIngestionService, Evidence, RetrievalService


def build_application_runtime(system: Any, *, observability=None) -> ApplicationRuntime:
    """Build the canonical application runtime around maintained services."""
    return ApplicationRuntime(
        {
            Capability.QUESTION: _question_handler(system),
            Capability.UPLOAD: _upload_handler(system),
            Capability.INDEX_STATUS: _index_status_handler(system),
        },
        observability=observability,
    )


def _question_handler(system: Any):
    async def handle(request: ApplicationRequest):
        result = await RetrievalService(system).answer(request.question)
        return {
            "response_text": result.response_text,
            "metadata": result.metadata,
            "evidence": result.evidence,
        }

    return handle


def _upload_handler(system: Any):
    async def handle(request: ApplicationRequest):
        uploaded_files = request.payload.get("uploaded_files")
        if not isinstance(uploaded_files, list) or not uploaded_files:
            raise ValueError("payload.uploaded_files must be a non-empty list")
        indexer = getattr(system, "local_file_indexer", None)
        if indexer is None:
            raise TypeError("maintained agent system must expose local_file_indexer")
        result = await DocumentIngestionService(indexer).ingest(uploaded_files)
        return {
            "response_text": _ingestion_message(result),
            "metadata": result.raw_metadata,
        }

    return handle


def _index_status_handler(system: Any):
    async def handle(request: ApplicationRequest):
        task_id = request.payload.get("task_id")
        return system.check_indexing_status(task_id)

    return handle


def _ingestion_message(result) -> str:
    indexed = sum(item.status == "indexed" for item in result.artifacts)
    skipped = sum(item.status == "skipped" for item in result.artifacts)
    failed = sum(item.status == "failed" for item in result.artifacts)
    if failed:
        raise RuntimeError(f"Document ingestion failed for {failed} artifact(s).")
    return f"Document ingestion completed: {indexed} indexed, {skipped} unchanged."
