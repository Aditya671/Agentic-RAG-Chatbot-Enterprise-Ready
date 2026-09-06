"""Adapters from maintained implementations into the application boundary."""
from __future__ import annotations

import re
from typing import Any

from .application_runtime import ApplicationRequest, ApplicationRuntime, Capability
from .reliability import RetrievalService


_TASK_ID_PATTERN = re.compile(r"Task ID is:\s*([A-Za-z0-9._:-]+)", re.IGNORECASE)


def build_application_runtime(
    system: Any, *, observability=None, conversation_store=None
) -> ApplicationRuntime:
    """Build the canonical application runtime around maintained services."""
    return ApplicationRuntime(
        {
            Capability.QUESTION: _question_handler(system),
            Capability.UPLOAD: _upload_handler(system),
            Capability.INDEX_STATUS: _index_status_handler(system),
        },
        observability=observability,
        conversation_store=conversation_store,
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


def _extract_task_id(value: Any) -> str:
    """Normalize maintained upload submission responses to the task-id contract."""
    if not isinstance(value, str) or not value.strip():
        raise TypeError("background indexing submission must return a task ID")
    value = value.strip()
    match = _TASK_ID_PATTERN.search(value)
    if match:
        return match.group(1)
    return value


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

        submission = await submit(uploaded_files)
        task_id = _extract_task_id(submission)

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
