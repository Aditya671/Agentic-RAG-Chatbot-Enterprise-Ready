"""Compatibility wrapper for uploaded files.

The wrapper is intentionally small: it represents an uploaded file while
keeping the actual file bytes on disk until ``read()`` is called.

The public attribute names from the original implementation are preserved:
``name``, ``path``, ``content`` and ``createdAt``.
"""

from __future__ import annotations

from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any, Dict, Optional, Union

PathValue = Union[str, PathLike[str]]
ContentValue = Optional[Union[bytes, bytearray, memoryview]]


class UploadedFileWrapper:
    """Represent an uploaded file and provide a file-like ``read`` method.

    ``content`` is retained for backwards compatibility. It is not implicitly
    populated from ``path`` because the original class treated it as an
    independent constructor value. Call ``read()`` when the on-disk content is
    required.
    """

    __slots__ = ("name", "path", "content", "createdAt")

    def __init__(
        self,
        path: PathValue,
        name: str,
        content: ContentValue,
        createdAt: Any,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string.")

        if isinstance(path, (str, PathLike)):
            normalized_path = Path(path)
        else:
            raise TypeError("path must be a string or path-like object.")

        if content is not None and not isinstance(
            content,
            (bytes, bytearray, memoryview),
        ):
            raise TypeError(
                "content must be bytes, bytearray, memoryview, or None."
            )

        self.name = name
        self.path = normalized_path
        self.content = content
        # Keep the original camelCase attribute for compatibility.
        self.createdAt = createdAt

    @property
    def created_at(self) -> Any:
        """PEP-8 alias while retaining the original ``createdAt`` contract."""
        return self.createdAt

    @created_at.setter
    def created_at(self, value: Any) -> None:
        self.createdAt = value

    @property
    def path_str(self) -> str:
        """Return the path in the representation expected by filesystem APIs."""
        return str(self.path)

    def read(self) -> bytes:
        """Read the current file bytes from disk.

        The method deliberately does not silently fall back to ``content``:
        callers of the original wrapper expect ``read()`` to reflect the file
        represented by ``path``.
        """
        with self.path.open("rb") as handle:
            return handle.read()

    def exists(self) -> bool:
        """Return whether the wrapped path currently exists as a regular file."""
        return self.path.is_file()

    def to_dict(self, *, include_content: bool = True) -> Dict[str, Any]:
        """Serialize the wrapper using the original field names.

        ``include_content=False`` is useful for queue/log metadata where copying
        potentially large file bytes is unnecessary.
        """
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
        """Reconstruct a wrapper from ``to_dict()`` compatible data."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary.")

        required = {"name", "path", "createdAt"}
        missing = required.difference(payload)
        if missing:
            raise ValueError(
                f"Missing required fields: {', '.join(sorted(missing))}"
            )

        return cls(
            path=payload["path"],
            name=payload["name"],
            content=payload.get("content"),
            createdAt=payload["createdAt"],
        )

    def __repr__(self) -> str:
        """Avoid dumping file contents into logs or tracebacks."""
        return (
            f"UploadedFileWrapper("
            f"name={self.name!r}, "
            f"path={str(self.path)!r}, "
            f"createdAt={self.createdAt!r})"
        )
