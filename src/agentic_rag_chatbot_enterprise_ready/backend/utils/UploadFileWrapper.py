"""Reconciled uploaded-file wrapper used by Chainlit and indexing paths."""

from __future__ import annotations

from datetime import datetime, timezone
from os import PathLike
from pathlib import Path
from typing import Any, Dict, Optional, Union

PathValue = Union[str, PathLike[str]]
ContentValue = Optional[Union[bytes, bytearray, memoryview]]


class UploadedFileWrapper:
    """Represent an uploaded file while preserving the historical API.

    ``content`` is optional and is retained as an in-memory upload payload.
    ``read()`` prefers that explicit payload when present, otherwise it reads
    the represented file from disk. This reconciles the original wrapper's
    file-backed behavior with the enhanced upload/indexer path that may carry
    bytes directly.
    """

    __slots__ = ("name", "path", "content", "createdAt")

    def __init__(
        self,
        path: PathValue,
        name: Optional[str] = None,
        content: ContentValue = None,
        createdAt: Optional[Any] = None,
    ) -> None:
        if not isinstance(path, (str, PathLike)):
            raise TypeError("path must be a string or path-like object.")
        normalized_path = Path(path)

        resolved_name = name or normalized_path.name
        if not isinstance(resolved_name, str) or not resolved_name.strip():
            raise ValueError("name must be a non-empty string.")

        if content is not None and not isinstance(content, (bytes, bytearray, memoryview)):
            raise TypeError("content must be bytes, bytearray, memoryview, or None.")

        self.name = resolved_name
        self.path = normalized_path
        self.content = content
        self.createdAt = createdAt or datetime.now(timezone.utc)

    @property
    def created_at(self) -> Any:
        return self.createdAt

    @created_at.setter
    def created_at(self, value: Any) -> None:
        self.createdAt = value

    @property
    def path_str(self) -> str:
        return str(self.path)

    def read(self) -> bytes:
        if self.content is not None:
            return bytes(self.content)
        with self.path.open("rb") as handle:
            return handle.read()

    def exists(self) -> bool:
        return self.path.is_file()

    def to_dict(self, *, include_content: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": self.name,
            "path": str(self.path),
            "createdAt": self.createdAt,
        }
        if include_content:
            payload["content"] = self.content
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "UploadedFileWrapper":
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary.")
        required = {"name", "path", "createdAt"}
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
        return cls(
            path=payload["path"],
            name=payload["name"],
            content=payload.get("content"),
            createdAt=payload["createdAt"],
        )

    def __repr__(self) -> str:
        return (
            f"UploadedFileWrapper(name={self.name!r}, "
            f"path={str(self.path)!r}, createdAt={self.createdAt!r})"
        )
