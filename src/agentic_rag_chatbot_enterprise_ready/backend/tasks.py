"""Celery application and asynchronous uploaded-file indexing task."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from typing import Any

from celery import Celery

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

from backend.user_uploaded_file_indexer import UserUploadedFileIndexer

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


def _validate_task_arguments(
    file_list: Sequence[str],
    root_dir: str,
    index_name: str,
    model: str,
    similarity_top_k: int,
) -> None:
    if isinstance(file_list, (str, bytes)) or not isinstance(file_list, Sequence):
        raise TypeError("file_list must be a sequence of file paths.")
    if not file_list:
        raise ValueError("file_list must not be empty.")
    if any(not isinstance(path, str) or not path.strip() for path in file_list):
        raise ValueError("file_list must contain only non-empty strings.")

    for value, name in (
        (root_dir, "root_dir"),
        (index_name, "index_name"),
        (model, "model"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string.")

    _positive_int(similarity_top_k, "similarity_top_k")


def _run_async(coro: Any) -> Any:
    """Run the indexer's coroutine inside the Celery worker boundary."""
    return asyncio.run(coro)


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
    file_list: list[str],
    root_dir: str,
    index_name: str,
    model: str,
    similarity_top_k: int,
) -> Any:
    """Index uploaded files asynchronously inside the worker process."""
    del self
    _validate_task_arguments(
        file_list=file_list,
        root_dir=root_dir,
        index_name=index_name,
        model=model,
        similarity_top_k=similarity_top_k,
    )

    logger.info(
        "Starting uploaded-file indexing: files=%d index=%s model=%s",
        len(file_list),
        index_name,
        model,
    )

    indexer = UserUploadedFileIndexer(
        root_dir=root_dir,
        index_name=index_name,
        model=model,
        memory=None,
        similarity_top_k=similarity_top_k,
    )

    try:
        result = _run_async(indexer.index_uploaded_files(file_list=list(file_list)))
    except Exception:
        logger.exception(
            "Uploaded-file indexing failed: files=%d index=%s",
            len(file_list),
            index_name,
        )
        raise

    logger.info(
        "Uploaded-file indexing completed: files=%d index=%s",
        len(file_list),
        index_name,
    )
    return result
