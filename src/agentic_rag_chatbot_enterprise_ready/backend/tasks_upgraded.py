"""Compatibility import for the historical upgraded task module."""

from .tasks import (
    DEFAULT_BROKER_URL,
    DEFAULT_RESULT_BACKEND,
    TASK_NAME,
    TASK_SOFT_TIME_LIMIT,
    TASK_TIME_LIMIT,
    _load_environment,
    _positive_int,
    _run_async,
    _validate_task_arguments,
    celery_app,
    index_files_task,
)

__all__ = [
    "DEFAULT_BROKER_URL",
    "DEFAULT_RESULT_BACKEND",
    "TASK_NAME",
    "TASK_SOFT_TIME_LIMIT",
    "TASK_TIME_LIMIT",
    "_load_environment",
    "_positive_int",
    "_run_async",
    "_validate_task_arguments",
    "celery_app",
    "index_files_task",
]
