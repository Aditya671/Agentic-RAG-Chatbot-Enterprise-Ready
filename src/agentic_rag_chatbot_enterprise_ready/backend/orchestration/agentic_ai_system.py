"""Canonical Agentic RAG runtime compatibility surface."""
from __future__ import annotations

from pathlib import Path

from .agentic_ai_system_upgraded import AsyncAgenticAiSystem as _ModernAsyncAgenticAiSystem


class AsyncAgenticAiSystem(_ModernAsyncAgenticAiSystem):
    """Expose the modern runtime while preserving the frontend upload contract."""

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
