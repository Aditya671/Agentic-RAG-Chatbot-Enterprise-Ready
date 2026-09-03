from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class UploadedFileWrapper:
    """Small adapter around Chainlit/user-uploaded files."""

    def __init__(
        self,
        path: str,
        name: Optional[str] = None,
        content: Optional[bytes] = None,
        createdAt: Optional[datetime] = None,
    ) -> None:
        self.path = str(path)
        self.name = name or Path(path).name
        self.content = content
        self.createdAt = createdAt or datetime.now(timezone.utc)

    def read(self) -> bytes:
        if self.content is not None:
            return bytes(self.content)
        return Path(self.path).read_bytes()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "content": self.read(),
            "createdAt": self.createdAt,
        }
