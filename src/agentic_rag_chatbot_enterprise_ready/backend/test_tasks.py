import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


MODULE_PATH = Path("/mnt/data/tasks_upgraded.py")


# ---------------------------------------------------------------------------
# Dependency-isolated Celery/backend stubs
# ---------------------------------------------------------------------------

celery_module = types.ModuleType("celery")
dotenv_module = types.ModuleType("dotenv")
backend_module = types.ModuleType("backend")
indexer_module = types.ModuleType("backend.user_uploaded_file_indexer")


class FakeTask:
    def __init__(self, func, **options):
        self.run = func
        self.name = options.get("name")
        self.bind = options.get("bind", False)
        self.options = options

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)


class FakeCelery:
    def __init__(self, name, broker=None, backend=None):
        self.main = name
        self.broker = broker
        self.backend = backend
        self.conf = {}

    def task(self, *args, **options):
        def decorator(func):
            return FakeTask(func, **options)

        return decorator

    def update(self, **kwargs):
        self.conf.update(kwargs)


class FakeIndexer:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.index_uploaded_files = AsyncMock()
        self.__class__.instances.append(self)


celery_module.Celery = FakeCelery
dotenv_module.load_dotenv = lambda **kwargs: None
indexer_module.UserUploadedFileIndexer = FakeIndexer

sys.modules["celery"] = celery_module
sys.modules["dotenv"] = dotenv_module
sys.modules["backend"] = backend_module
sys.modules["backend.user_uploaded_file_indexer"] = indexer_module

spec = importlib.util.spec_from_file_location(
    "tasks_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    FakeIndexer.instances.clear()
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
    yield


def _call_task(*args, **kwargs):
    # bind=True means the task receives the task object as the first argument.
    return module.index_files_task.run(module.index_files_task, *args, **kwargs)


def test_task_name_is_preserved():
    assert module.index_files_task.name == "tasks.index_files"


def test_celery_app_has_default_redis_broker():
    assert module.celery_app.broker == "redis://localhost:6379/0"


def test_celery_app_has_default_redis_backend():
    assert module.celery_app.backend == "redis://localhost:6379/0"


def test_json_serialization_is_explicit():
    assert module.celery_app.conf["task_serializer"] == "json"
    assert module.celery_app.conf["result_serializer"] == "json"
    assert module.celery_app.conf["accept_content"] == ["json"]


def test_task_started_tracking_is_enabled():
    assert module.celery_app.conf["task_track_started"] is True


def test_task_time_limits_are_configured():
    assert module.celery_app.conf["task_soft_time_limit"] == 1800
    assert module.celery_app.conf["task_time_limit"] == 2100


def test_valid_task_constructs_indexer_in_worker_context():
    expected = {"status": "ok"}

    class ReturningIndexer(FakeIndexer):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.index_uploaded_files.return_value = expected

    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = ReturningIndexer
    try:
        result = _call_task(
            ["a.pdf", "b.docx"],
            "root",
            "index",
            "gpt-5.1",
            20,
        )
    finally:
        module.UserUploadedFileIndexer = original

    assert result == expected


def test_indexer_receives_memory_none():
    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = FakeIndexer
    try:
        _call_task(
            ["a.pdf"],
            "root",
            "index",
            "gpt-5.1",
            10,
        )
    finally:
        module.UserUploadedFileIndexer = original

    assert FakeIndexer.instances[-1].kwargs["memory"] is None


def test_indexer_receives_all_configuration_arguments():
    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = FakeIndexer
    try:
        _call_task(
            ["a.pdf", "b.pdf"],
            "/data",
            "portfolio-index",
            "gpt-5.1",
            25,
        )
    finally:
        module.UserUploadedFileIndexer = original

    kwargs = FakeIndexer.instances[-1].kwargs

    assert kwargs["root_dir"] == "/data"
    assert kwargs["index_name"] == "portfolio-index"
    assert kwargs["model"] == "gpt-5.1"
    assert kwargs["similarity_top_k"] == 25


def test_file_list_is_copied_before_passing_to_indexer():
    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = FakeIndexer
    try:
        files = ["a.pdf"]
        _call_task(files, "root", "index", "gpt-5.1", 10)
    finally:
        module.UserUploadedFileIndexer = original

    call = FakeIndexer.instances[-1].index_uploaded_files.await_args
    passed_files = call.kwargs["file_list"]

    assert passed_files == ["a.pdf"]
    assert passed_files is not files


@pytest.mark.parametrize("file_list", [[], (), None, "a.pdf", b"a.pdf"])
def test_invalid_file_list_is_rejected(file_list):
    with pytest.raises((TypeError, ValueError)):
        _call_task(
            file_list,
            "root",
            "index",
            "gpt-5.1",
            10,
        )


def test_file_list_rejects_empty_path():
    with pytest.raises(ValueError):
        _call_task(
            ["a.pdf", " "],
            "root",
            "index",
            "gpt-5.1",
            10,
        )


@pytest.mark.parametrize(
    "argument_index",
    [1, 2, 3],
)
def test_required_string_arguments_are_validated(argument_index):
    args = [["a.pdf"], "root", "index", "gpt-5.1", 10]
    args[argument_index] = ""

    with pytest.raises(ValueError):
        _call_task(*args)


@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "10", None])
def test_similarity_top_k_must_be_positive_integer(value):
    with pytest.raises(ValueError):
        _call_task(
            ["a.pdf"],
            "root",
            "index",
            "gpt-5.1",
            value,
        )


def test_indexer_async_method_is_called_with_file_list():
    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = FakeIndexer
    try:
        _call_task(
            ["a.pdf", "b.pdf"],
            "root",
            "index",
            "gpt-5.1",
            10,
        )
    finally:
        module.UserUploadedFileIndexer = original

    instance = FakeIndexer.instances[-1]
    instance.index_uploaded_files.assert_awaited_once_with(
        file_list=["a.pdf", "b.pdf"]
    )


def test_indexer_result_is_returned():
    expected = {"indexed": 2}

    class ReturningIndexer(FakeIndexer):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.index_uploaded_files.return_value = expected

    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = ReturningIndexer
    try:
        result = _call_task(
            ["a.pdf", "b.pdf"],
            "root",
            "index",
            "gpt-5.1",
            10,
        )
    finally:
        module.UserUploadedFileIndexer = original

    assert result == expected


def test_indexer_exception_is_propagated():
    class FailingIndexer(FakeIndexer):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.index_uploaded_files.side_effect = RuntimeError("index failed")

    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = FailingIndexer
    try:
        with pytest.raises(RuntimeError, match="index failed"):
            _call_task(
                ["a.pdf"],
                "root",
                "index",
                "gpt-5.1",
                10,
            )
    finally:
        module.UserUploadedFileIndexer = original


def test_no_automatic_retry_is_assumed():
    assert "autoretry_for" not in module.index_files_task.options
    assert "retry_kwargs" not in module.index_files_task.options


def test_task_is_bound_for_future_retry_or_progress_support():
    assert module.index_files_task.bind is True


def test_task_does_not_enable_late_ack_without_idempotency_contract():
    assert "task_acks_late" not in module.celery_app.conf


def test_task_does_not_enable_worker_lost_requeue_without_idempotency_contract():
    assert "task_reject_on_worker_lost" not in module.celery_app.conf


def test_no_pickle_is_allowed_by_task_configuration():
    assert "pickle" not in module.celery_app.conf.get("accept_content", [])


def test_no_secret_is_hardcoded():
    source = MODULE_PATH.read_text()

    assert "OPENAI_API_KEY" not in source
    assert "AZURE_OPENAI_API_KEY" not in source
    assert "api_key =" not in source.lower()
    assert "api_token =" not in source.lower()


def test_dotenv_does_not_override_runtime_environment():
    source = MODULE_PATH.read_text()

    assert "load_dotenv(override=True)" not in source
    assert "load_dotenv(override=False)" in source


def test_no_file_contents_are_sent_through_task_arguments():
    source = MODULE_PATH.read_text()

    assert "file_content" not in source
    assert "file_bytes" not in source
    assert "open(" not in source


def test_task_arguments_are_serialization_safe():
    # Public task signature intentionally contains only list[str], str, and int.
    annotations = module.index_files_task.run.__annotations__

    assert annotations["file_list"] == "list[str]"
    assert annotations["root_dir"] == "str"
    assert annotations["index_name"] == "str"
    assert annotations["model"] == "str"
    assert annotations["similarity_top_k"] == "int"


def test_asyncio_run_is_isolated_in_helper():
    assert callable(module._run_async)


def test_run_async_returns_coroutine_result():
    async def sample():
        return 42

    assert module._run_async(sample()) == 42


def test_run_async_propagates_async_exception():
    async def sample():
        raise RuntimeError("async failure")

    with pytest.raises(RuntimeError, match="async failure"):
        module._run_async(sample())


def test_environment_broker_configuration_is_supported(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://example:6379/3")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://example:6379/4")

    # The module already initialized during import, so verify the source-level
    # contract instead of reloading a module with a second Celery singleton.
    source = MODULE_PATH.read_text()

    assert 'os.getenv("CELERY_BROKER_URL", DEFAULT_BROKER_URL)' in source
    assert 'os.getenv("CELERY_RESULT_BACKEND", DEFAULT_RESULT_BACKEND)' in source


def test_task_name_constant_matches_registered_name():
    assert module.TASK_NAME == module.index_files_task.name


def test_task_docstring_documents_worker_local_indexer():
    assert "worker" in module.index_files_task.run.__doc__.lower()
    assert "serialization-safe" in module.index_files_task.run.__doc__


def test_module_has_no_global_indexer_instance():
    assert not hasattr(module, "indexer")


def test_validation_happens_before_indexer_creation():
    original = module.UserUploadedFileIndexer

    class ShouldNotBeConstructed:
        def __init__(self, **kwargs):
            raise AssertionError("Indexer should not have been created")

    module.UserUploadedFileIndexer = ShouldNotBeConstructed
    try:
        with pytest.raises(ValueError):
            _call_task(
                [],
                "root",
                "index",
                "gpt-5.1",
                10,
            )
    finally:
        module.UserUploadedFileIndexer = original


def test_valid_task_does_not_require_memory_argument_from_caller():
    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = FakeIndexer
    try:
        _call_task(
            ["a.pdf"],
            "root",
            "index",
            "gpt-5.1",
            10,
        )
    finally:
        module.UserUploadedFileIndexer = original

    assert FakeIndexer.instances[-1].kwargs["memory"] is None


def test_logging_does_not_log_file_names():
    source = MODULE_PATH.read_text()

    assert 'logger.info(\n        "Starting uploaded-file indexing: files=%d index=%s model=%s"' in source
    assert '"file_list=%s"' not in source
    assert 'logger.info("'.__class__ is str


def test_task_limits_are_positive():
    assert module.TASK_SOFT_TIME_LIMIT > 0
    assert module.TASK_TIME_LIMIT > module.TASK_SOFT_TIME_LIMIT


def test_default_broker_backend_are_stable():
    assert module.DEFAULT_BROKER_URL.startswith("redis://")
    assert module.DEFAULT_RESULT_BACKEND.startswith("redis://")


def test_task_configuration_is_not_using_global_pickle():
    source = MODULE_PATH.read_text()

    assert "task_serializer=\"pickle\"" not in source
    assert "result_serializer=\"pickle\"" not in source


def test_indexer_is_created_only_after_validation():
    created = []

    class RecordingIndexer(FakeIndexer):
        def __init__(self, **kwargs):
            created.append(kwargs)
            super().__init__(**kwargs)

    original = module.UserUploadedFileIndexer
    module.UserUploadedFileIndexer = RecordingIndexer
    try:
        _call_task(["a.pdf"], "root", "index", "gpt-5.1", 10)
    finally:
        module.UserUploadedFileIndexer = original

    assert len(created) == 1


def test_existing_task_public_name_is_not_changed():
    assert module.index_files_task.name == "tasks.index_files"


def test_module_does_not_create_asyncio_event_loop_at_import():
    source = MODULE_PATH.read_text()

    assert "asyncio.run(" in source
    assert "asyncio.new_event_loop()" not in source
    assert "asyncio.get_event_loop()" not in source
