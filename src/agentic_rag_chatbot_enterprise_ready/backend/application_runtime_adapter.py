"""Adapters from maintained implementations into the application boundary."""
from __future__ import annotations

from typing import Any

from .application_runtime import ApplicationRequest, ApplicationRuntime, Capability
from .reliability import RetrievalService


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

        submit = getattr(system, "upload_and_index_files_async", None)
        if not callable(submit):
            raise TypeError(
                "maintained agent system must expose upload_and_index_files_async"
            )

        task_id = await submit(uploaded_files)
        if not isinstance(task_id, str) or not task_id.strip():
            raise TypeError("background indexing submission must return a task ID")

        return {
            "response_text": f"Document indexing task submitted: {task_id}",
            "metadata": {
                "task_id": task_id,
                "status": "submitted",
                "artifact_count": len(uploaded_files),
            },
        }

    return handle


def _index_status_handler(system: Any):
    async def handle(request: ApplicationRequest):
        task_id = request.payload.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("payload.task_id must be a non-empty string")
        return {
            "response_text": str(system.check_indexing_status(task_id)),
            "metadata": {"task_id": task_id},
        }

    return handle
