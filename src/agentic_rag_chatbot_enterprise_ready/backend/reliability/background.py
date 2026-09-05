"""Provider-neutral contracts for asynchronous ingestion and idempotency.

Phase 73 separates artifact identity, task identity, and execution outcome.
The existing uploaded-file indexer remains the canonical indexing implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import re
from typing import Any, Mapping, Protocol, Sequence


class TaskStatus(StrEnum):
    """Lifecycle states for a background indexing task."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FailureClass(StrEnum):
    """Deterministic failure classification used by retry policy."""

    RETRYABLE = "retryable"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """Stable identity for one uploaded artifact."""

    artifact_id: str
    filename: str
    checksum: str
    identity_version: str = "v1"


@dataclass(frozen=True, slots=True)
class BackgroundTask:
    """Provider-neutral description of one asynchronous indexing attempt."""

    task_id: str
    artifact_ids: tuple[str, ...]
    operation: str = "index"
    status: TaskStatus = TaskStatus.QUEUED
    attempt: int = 1
    run_id: str | None = None
    error_class: FailureClass | None = None
    error_type: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class BackgroundTaskStore(Protocol):
    """Persistence boundary for background task state."""

    async def put(self, task: BackgroundTask) -> None: ...

    async def get(self, task_id: str) -> BackgroundTask | None: ...


class ArtifactIdempotencyStore(Protocol):
    """Persistence boundary for completed artifact operations."""

    async def get(self, key: str) -> Mapping[str, Any] | None: ...

    async def put(self, key: str, result: Mapping[str, Any]) -> None: ...


class InMemoryBackgroundTaskStore:
    """Deterministic task store for tests and local development."""

    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}

    async def put(self, task: BackgroundTask) -> None:
        if not isinstance(task.task_id, str) or not task.task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        self._tasks[task.task_id] = task

    async def get(self, task_id: str) -> BackgroundTask | None:
        return self._tasks.get(task_id)


class InMemoryArtifactIdempotencyStore:
    """Deterministic completed-operation store for contract tests."""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> Mapping[str, Any] | None:
        return self._results.get(key)

    async def put(self, key: str, result: Mapping[str, Any]) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("idempotency key must be a non-empty string")
        self._results[key] = dict(result)


def normalize_artifact_filename(filename: str) -> str:
    """Normalize identity-relevant filename variation without trusting paths."""
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty string")
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name)
    if not name or name in {".", ".."}:
        raise ValueError("invalid filename")
    return name


def build_artifact_identity(
    filename: str,
    checksum: str,
    *,
    identity_version: str = "v1",
) -> ArtifactIdentity:
    """Build a deterministic identity from content and logical filename."""
    normalized_name = normalize_artifact_filename(filename)
    if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
        raise ValueError("checksum must be a SHA-256 hexadecimal digest")
    if not isinstance(identity_version, str) or not identity_version.strip():
        raise ValueError("identity_version must be a non-empty string")

    material = f"{identity_version}:{normalized_name}:{checksum.lower()}".encode("utf-8")
    artifact_id = hashlib.sha256(material).hexdigest()
    return ArtifactIdentity(
        artifact_id=artifact_id,
        filename=normalized_name,
        checksum=checksum.lower(),
        identity_version=identity_version,
    )


def artifact_idempotency_key(
    artifact: ArtifactIdentity,
    *,
    operation: str = "index",
    scope: str = "default",
) -> str:
    """Return a stable operation key scoped to its destination/context."""
    for value, name in ((operation, "operation"), (scope, "scope")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    return f"{artifact.identity_version}:{scope}:{operation}:{artifact.artifact_id}"


def classify_failure(exc: BaseException) -> FailureClass:
    """Classify common deterministic input failures separately from infrastructure failures."""
    if isinstance(exc, (ValueError, TypeError, FileNotFoundError, PermissionError)):
        return FailureClass.TERMINAL
    return FailureClass.RETRYABLE


def artifact_identities_from_paths(
    file_paths: Sequence[str],
    checksums: Mapping[str, str],
    *,
    identity_version: str = "v1",
) -> tuple[ArtifactIdentity, ...]:
    """Create deterministic identities when the upload boundary already has hashes."""
    if not file_paths:
        raise ValueError("file_paths must not be empty")
    identities: list[ArtifactIdentity] = []
    for path in file_paths:
        normalized = normalize_artifact_filename(path)
        checksum = checksums.get(path) or checksums.get(normalized)
        if checksum is None:
            raise ValueError(f"missing checksum for artifact: {path}")
        identities.append(
            build_artifact_identity(normalized, checksum, identity_version=identity_version)
        )
    return tuple(identities)
