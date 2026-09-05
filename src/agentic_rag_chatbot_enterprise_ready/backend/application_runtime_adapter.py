"""Adapters from the maintained agent implementation into the application boundary."""
from __future__ import annotations

from typing import Any

from .application_runtime import ApplicationRequest, ApplicationRuntime, Capability
from .reliability import Evidence


def build_application_runtime(system: Any, *, observability=None) -> ApplicationRuntime:
    """Build the canonical application runtime around a maintained agent system."""
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
        response = await system.get_response(request.question)
        if not isinstance(response, dict):
            return str(response)
        metadata = response.get("response_metadata", [])
        return {
            "response_text": response.get("response_text", ""),
            "metadata": metadata if isinstance(metadata, dict) else {"sources": metadata},
            "evidence": tuple(_evidence_from_source(source) for source in _source_items(metadata)),
        }

    return handle


def _upload_handler(system: Any):
    async def handle(request: ApplicationRequest):
        uploaded_files = request.payload.get("uploaded_files")
        if not isinstance(uploaded_files, list):
            raise ValueError("payload.uploaded_files must be a list")
        return await system.upload_and_index_files(uploaded_files)

    return handle


def _index_status_handler(system: Any):
    async def handle(request: ApplicationRequest):
        task_id = request.payload.get("task_id")
        return system.check_indexing_status(task_id)

    return handle


def _source_items(metadata: Any) -> list[Any]:
    if isinstance(metadata, dict):
        sources = metadata.get("sources", metadata.get("source_nodes", metadata))
    else:
        sources = metadata
    if isinstance(sources, (list, tuple)):
        return list(sources)
    return []


def _evidence_from_source(source: Any) -> Evidence:
    if not isinstance(source, dict):
        raise TypeError("retrieval metadata source must be a mapping")
    source_id = str(
        source.get("id")
        or source.get("source")
        or source.get("file_name")
        or source.get("filename")
        or "unknown"
    )
    locator = source.get("locator") or source.get("page") or source.get("url")
    score = source.get("score")
    relevance = float(score) if isinstance(score, (int, float)) else None
    metadata = {
        key: value
        for key, value in source.items()
        if key not in {"content", "excerpt", "text"}
    }
    return Evidence(
        source_id=source_id,
        source_type=str(source.get("type") or "retrieval"),
        locator=str(locator) if locator is not None else None,
        relevance=relevance,
        metadata=metadata,
    )
