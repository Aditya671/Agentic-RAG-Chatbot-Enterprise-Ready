"""Canonical Agentic RAG runtime compatibility surface.

The historical module path remains stable for existing callers, but the
runtime implementation is now the converged provider-boundary implementation.
The older ``agentic_ai_system_upgraded`` module is retained as an internal
migration source rather than as the preferred application entry point.
"""
from __future__ import annotations

from pathlib import Path

from .integrated_agent_system import IntegratedAsyncAgenticAiSystem


class AsyncAgenticAiSystem(IntegratedAsyncAgenticAiSystem):
    """Expose the converged runtime while preserving the legacy API surface."""

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

        status = await self.upload_and_index_files_async(payload)
        return {item["name"]: status for item in payload}


__all__ = ["AsyncAgenticAiSystem"]
