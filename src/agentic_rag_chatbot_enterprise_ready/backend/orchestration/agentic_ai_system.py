"""Canonical Agentic RAG runtime compatibility surface.

The historical module path remains stable for existing callers, but the
runtime implementation is now the converged provider-boundary implementation.
The older ``agentic_ai_system_upgraded`` module is retained as an internal
migration source rather than as the preferred application entry point.
"""
from __future__ import annotations

import re
from pathlib import Path

from .integrated_agent_system import IntegratedAsyncAgenticAiSystem


_TASK_ID_PATTERN = re.compile(r"Task ID is:\s*([A-Za-z0-9._:-]+)", re.IGNORECASE)


class AsyncAgenticAiSystem(IntegratedAsyncAgenticAiSystem):
    """Expose the converged runtime while preserving the legacy API surface."""

    async def upload_and_index_files_async(self, uploaded_files):
        """Return the stable background task ID for application callers."""
        submission = await super().upload_and_index_files_async(uploaded_files)
        match = _TASK_ID_PATTERN.search(str(submission))
        if match:
            return match.group(1)
        if isinstance(submission, str) and submission.strip():
            return submission.strip()
        raise RuntimeError("Background indexing submission did not return a task ID.")

    async def upload_and_index_files(self, uploaded_files):
        """Accept Chainlit upload wrappers and dispatch them to the async indexer."""
        if not isinstance(uploaded_files, list) or not uploaded_files:
            raise ValueError("uploaded_files must be a non-empty list.")

        payload = []
        for uploaded_file in uploaded_files:
            name = getattr(uploaded_file, "name", None) or Path(
                getattr(uploaded_file, "path", "")
            ).name
            content = getattr(uploaded_file, "content", None)
            if content is None:
                path = getattr(uploaded_file, "path", None)
                if not path:
                    raise ValueError(f"File '{name}' has no readable path or content.")
                content = Path(path).read_bytes()
            payload.append({"name": name, "content": content})

        task_id = await self.upload_and_index_files_async(payload)
        return {item["name"]: task_id for item in payload}


__all__ = ["AsyncAgenticAiSystem"]
