from unittest.mock import AsyncMock, Mock

import pytest

from agentic_rag_chatbot_enterprise_ready.backend import tasks as module


class FakeIndexer:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.index_uploaded_files = AsyncMock()
        self.__class__.instances.append(self)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    FakeIndexer.instances.clear()
    monkeypatch.setattr(module, "UserUploadedFileIndexer", FakeIndexer)


def call_task(*args):
    return module.index_files_task.run(module.index_files_task, *args)


def test_task_name_is_preserved():
    assert module.index_files_task.name == "tasks.index_files"


def test_compatibility_module_points_to_canonical_implementation():
    from agentic_rag_chatbot_enterprise_ready.backend import tasks_upgraded

    assert tasks_upgraded.index_files_task is module.index_files_task
    assert tasks_upgraded.celery_app is module.celery_app


def test_json_serialization_is_explicit():
    assert module.celery_app.conf.task_serializer == "json"
    assert module.celery_app.conf.result_serializer == "json"
    assert module.celery_app.conf.accept_content == ["json"]


def test_started_tracking_and_time_limits_are_configured():
    assert module.celery_app.conf.task_track_started is True
    assert module.celery_app.conf.task_soft_time_limit == 1800
    assert module.celery_app.conf.task_time_limit == 2100


def test_valid_task_constructs_worker_local_indexer():
    expected = {"status": "ok"}
    FakeIndexer.instances.append = Mock()
    # Use the actual class list through a separate implementation to avoid
    # changing the assertion surface of the task itself.
    class ReturningIndexer(FakeIndexer):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.index_uploaded_files.return_value = expected

    module.UserUploadedFileIndexer = ReturningIndexer
    result = call_task(["a.pdf"], "root", "index", "gpt-5.1", 10)
    assert result == expected


def test_indexer_receives_expected_configuration():
    call_task(["a.pdf", "b.pdf"], "/data", "portfolio", "gpt-5.1", 25)
    kwargs = FakeIndexer.instances[-1].kwargs
    assert kwargs == {
        "root_dir": "/data",
        "index_name": "portfolio",
        "model": "gpt-5.1",
        "memory": None,
        "similarity_top_k": 25,
    }


def test_file_list_is_copied_before_async_call():
    files = ["a.pdf"]
    call_task(files, "root", "index", "gpt-5.1", 10)
    passed = FakeIndexer.instances[-1].index_uploaded_files.await_args.kwargs["file_list"]
    assert passed == files
    assert passed is not files


@pytest.mark.parametrize("value", [[], (), None, "a.pdf", b"a.pdf"])
def test_invalid_file_list_is_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        call_task(value, "root", "index", "gpt-5.1", 10)


@pytest.mark.parametrize("value", ["", None, 10])
def test_string_arguments_are_validated(value):
    with pytest.raises(ValueError):
        call_task(["a.pdf"], value, "index", "gpt-5.1", 10)


@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "10", None])
def test_similarity_top_k_must_be_positive_integer(value):
    with pytest.raises(ValueError):
        call_task(["a.pdf"], "root", "index", "gpt-5.1", value)


def test_empty_file_path_is_rejected():
    with pytest.raises(ValueError):
        call_task(["a.pdf", " "], "root", "index", "gpt-5.1", 10)


def test_indexer_is_called_once_with_file_list():
    call_task(["a.pdf", "b.pdf"], "root", "index", "gpt-5.1", 10)
    FakeIndexer.instances[-1].index_uploaded_files.assert_awaited_once_with(
        file_list=["a.pdf", "b.pdf"]
    )


def test_indexer_result_is_returned():
    expected = {"indexed": 2}

    class ReturningIndexer(FakeIndexer):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.index_uploaded_files.return_value = expected

    module.UserUploadedFileIndexer = ReturningIndexer
    assert call_task(["a.pdf", "b.pdf"], "root", "index", "gpt-5.1", 10) == expected


def test_indexer_exception_is_propagated():
    class FailingIndexer(FakeIndexer):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.index_uploaded_files.side_effect = RuntimeError("index failed")

    module.UserUploadedFileIndexer = FailingIndexer
    with pytest.raises(RuntimeError, match="index failed"):
        call_task(["a.pdf"], "root", "index", "gpt-5.1", 10)


def test_task_is_bound():
    assert module.index_files_task.bind is True


def test_automatic_retry_is_not_enabled():
    assert "autoretry_for" not in module.index_files_task.__dict__


def test_task_does_not_opt_into_late_ack_without_idempotency_contract():
    assert module.celery_app.conf.task_acks_late is False


def test_default_broker_and_backend_are_redis():
    assert module.DEFAULT_BROKER_URL.startswith("redis://")
    assert module.DEFAULT_RESULT_BACKEND.startswith("redis://")


def test_async_boundary_is_isolated():
    async def sample():
        return 42

    assert module._run_async(sample()) == 42


def test_validation_happens_before_indexer_creation():
    constructor = Mock(side_effect=AssertionError("must not construct"))
    module.UserUploadedFileIndexer = constructor
    with pytest.raises(ValueError):
        call_task([], "root", "index", "gpt-5.1", 10)
    constructor.assert_not_called()
