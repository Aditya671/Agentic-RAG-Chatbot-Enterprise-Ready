"""Celery application and asynchronous uploaded-file indexing task."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from typing import Any, Mapping

from celery import Celery

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

from backend.reliability.background import (
    ArtifactIdentity,
    artifact_idempotency_key,
    build_artifact_identity,
)
from backend.user_uploaded_file_indexer import UserUploadedFileIndexer
from backend.utility import compute_file_hash

logger = logging.getLogger(__name__)

TASK_NAME = "tasks.index_files"
DEFAULT_BROKER_URL = "redis://localhost:6379/0"
DEFAULT_RESULT_BACKEND = "redis://localhost:6379/0"


def _load_environment() -> None:
    """Load local .env values without overriding runtime configuration."""
    if load_dotenv is not None:
        load_dotenv(override=False)


_load_environment()


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    return _positive_int(value, name)


TASK_SOFT_TIME_LIMIT = _env_positive_int("CELERY_INDEX_SOFT_TIME_LIMIT", 1800)
TASK_TIME_LIMIT = _env_positive_int("CELERY_INDEX_TIME_LIMIT", 2100)
if TASK_SOFT_TIME_LIMIT >= TASK_TIME_LIMIT:
    raise ValueError("CELERY_INDEX_SOFT_TIME_LIMIT must be less than CELERY_INDEX_TIME_LIMIT.")


def _normalize_file_paths(file_list: Sequence[Any]) -> list[str]:
    """Normalize legacy task dictionaries and canonical path payloads."""
    normalized: list[str] = []
    for item in file_list:
        if isinstance(item, str) and item.strip():
            normalized.append(item)
            continue
        if isinstance(item, Mapping):
            path = item.get("path")
            if isinstance(path, str) and path.strip():
                normalized.append(path)
                continue
        raise ValueError("file_list items must be non-empty paths or mappings with 'path'.")
    return normalized


def _validate_task_arguments(
    file_list: Sequence[Any],
    root_dir: str,
    index_name: str,
    model: str,
    similarity_top_k: int,
    artifact_ids: Sequence[str] | None = None,
) -> list[str]:
    if isinstance(file_list, (str, bytes)) or not isinstance(file_list, Sequence):
        raise TypeError("file_list must be a sequence of file paths.")
    if not file_list:
        raise ValueError("file_list must not be empty.")

    normalized_paths = _normalize_file_paths(file_list)

    for value, name in (
        (root_dir, "root_dir"),
        (index_name, "index_name"),
        (model, "model"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string.")

    _positive_int(similarity_top_k, "similarity_top_k")

    if artifact_ids is not None:
        if isinstance(artifact_ids, (str, bytes)) or not isinstance(artifact_ids, Sequence):
            raise TypeError("artifact_ids must be a sequence when supplied.")
        if len(artifact_ids) != len(normalized_paths):
            raise ValueError("artifact_ids must contain one identity per file.")
        if any(not isinstance(value, str) or not value.strip() for value in artifact_ids):
            raise ValueError("artifact_ids must contain only non-empty strings.")

    return normalized_paths


def _run_async(coro: Any) -> Any:
    """Run the indexer's coroutine inside the Celery worker boundary."""
    return asyncio.run(coro)


def _artifact_identities(file_list: Sequence[str]) -> tuple[ArtifactIdentity, ...]:
    identities: list[ArtifactIdentity] = []
    for path in file_list:
        checksum = compute_file_hash(path)
        identities.append(build_artifact_identity(path, checksum))
    return tuple(identities)


celery_app = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", DEFAULT_BROKER_URL),
    backend=os.getenv("CELERY_RESULT_BACKEND", DEFAULT_RESULT_BACKEND),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT,
    task_time_limit=TASK_TIME_LIMIT,
)


@celery_app.task(name=TASK_NAME, bind=True)
def index_files_task(
    self: Any,
    file_list: list[Any],
    root_dir: str,
    index_name: str,
    model: str,
    similarity_top_k: int,
    artifact_ids: list[str] | None = None,
    run_id: str | None = None,
) -> Any:
    """Index uploaded files with stable artifact/task correlation.

    The task does not enable automatic retries. The maintained indexer's
    hash/version-aware skip behavior remains the canonical idempotency
    mechanism until a durable artifact-operation store exists.
    """
    normalized_paths = _validate_task_arguments(
        file_list=file_list,
        root_dir=root_dir,
        index_name=index_name,
        model=model,
        similarity_top_k=similarity_top_k,
        artifact_ids=artifact_ids,
    )

    identities = _artifact_identities(normalized_paths)
    derived_ids = [identity.artifact_id for identity in identities]
    if artifact_ids is not None and list(artifact_ids) != derived_ids:
        raise ValueError("artifact_ids do not match the current file content identities.")

    task_id = str(getattr(getattr(self, "request", None), "id", ""))
    idempotency_keys = [
        artifact_idempotency_key(identity, scope=index_name) for identity in identities
    ]

    logger.info(
        "Starting uploaded-file indexing: task_id=%s run_id=%s files=%d index=%s "
        "artifact_ids=%s idempotency_keys=%s",
        task_id,
        run_id or "",
        len(normalized_paths),
        index_name,
        derived_ids,
        idempotency_keys,
    )

    indexer = UserUploadedFileIndexer(
        root_dir=root_dir,
        index_name=index_name,
        model=model,
        memory=None,
        similarity_top_k=similarity_top_k,
    )

    try:
        result = _run_async(indexer.index_uploaded_files(file_list=list(normalized_paths)))
    except Exception:
        logger.exception(
            "Uploaded-file indexing failed: task_id=%s run_id=%s files=%d index=%s "
            "artifact_ids=%s",
            task_id,
            run_id or "",
            len(normalized_paths),
            index_name,
            derived_ids,
        )
        raise

    logger.info(
        "Uploaded-file indexing completed: task_id=%s run_id=%s files=%d index=%s "
        "artifact_ids=%s",
        task_id,
        run_id or "",
        len(normalized_paths),
        index_name,
        derived_ids,
    )
    return result
