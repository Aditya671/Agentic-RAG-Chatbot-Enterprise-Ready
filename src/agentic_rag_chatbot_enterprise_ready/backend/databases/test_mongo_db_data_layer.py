import base64
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest


MODULE_PATH = Path("/mnt/data/mongo_db_data_layer_upgraded.py")


# Dependency-isolated stubs for PyMongo and Chainlit.
pymongo_module = types.ModuleType("pymongo")
pymongo_errors_module = types.ModuleType("pymongo.errors")
chainlit_module = types.ModuleType("chainlit")
chainlit_data_module = types.ModuleType("chainlit.data")
chainlit_data_base_module = types.ModuleType("chainlit.data.base")
chainlit_data_utils_module = types.ModuleType("chainlit.data.utils")
chainlit_element_module = types.ModuleType("chainlit.element")
chainlit_step_module = types.ModuleType("chainlit.step")
chainlit_types_module = types.ModuleType("chainlit.types")


class FakeDuplicateKeyError(Exception):
    pass


class FakeAsyncMongoClient:
    instances = []

    def __init__(self, connection_string, **kwargs):
        self.connection_string = connection_string
        self.kwargs = kwargs
        self.closed = False
        self.databases = {}
        self.__class__.instances.append(self)

    def __getitem__(self, name):
        self.databases.setdefault(name, FakeDatabase())
        return self.databases[name]

    async def close(self):
        self.closed = True


class FakeDatabase:
    def __getitem__(self, name):
        return FakeCollection()


class FakeCollection:
    def __init__(self):
        self.create_indexes = AsyncMock()
        self.find_one = AsyncMock()
        self.insert_one = AsyncMock()
        self.update_one = AsyncMock()
        self.delete_one = AsyncMock()
        self.replace_one = AsyncMock()
        self.find = Mock()


class FakeBaseDataLayer:
    pass


def queue_until_user_message():
    def decorator(func):
        return func
    return decorator


class FakeUser:
    def __init__(self, identifier, metadata=None):
        self.identifier = identifier
        self.metadata = metadata or {}


class FakePersistedUser:
    def __init__(
        self,
        id,
        display_name,
        identifier,
        createdAt,
        metadata,
    ):
        self.id = id
        self.display_name = display_name
        self.identifier = identifier
        self.createdAt = createdAt
        self.metadata = metadata


class FakeFeedback:
    def __init__(
        self,
        id=None,
        forId="step-1",
        threadId="thread-1",
        value=1,
        comment="good",
        userId=None,
    ):
        self.id = id
        self.forId = forId
        self.threadId = threadId
        self.value = value
        self.comment = comment
        self.userId = userId


class FakeElement:
    def __init__(self, value):
        self.value = value

    def to_dict(self):
        return self.value


class FakePagination:
    def __init__(self, first=10, cursor=None):
        self.first = first
        self.cursor = cursor


class FakeThreadFilter:
    def __init__(self, userId=None, search=None):
        self.userId = userId
        self.search = search


class FakePageInfo:
    def __init__(self, hasNextPage, startCursor, endCursor):
        self.hasNextPage = hasNextPage
        self.startCursor = startCursor
        self.endCursor = endCursor


class FakePaginatedResponse:
    def __init__(self, data, pageInfo):
        self.data = data
        self.pageInfo = pageInfo


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sort_args = None
        self.limit_value = None

    def sort(self, *args):
        self.sort_args = args
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    async def to_list(self, length=None):
        return self.rows[:length] if length is not None else self.rows


pymongo_module.AsyncMongoClient = FakeAsyncMongoClient
pymongo_module.ASCENDING = 1
pymongo_module.DESCENDING = -1
pymongo_module.DuplicateKeyError = FakeDuplicateKeyError
pymongo_errors_module.DuplicateKeyError = FakeDuplicateKeyError

chainlit_module.User = FakeUser
chainlit_module.PersistedUser = FakePersistedUser
chainlit_data_base_module.BaseDataLayer = FakeBaseDataLayer
chainlit_data_utils_module.queue_until_user_message = queue_until_user_message
chainlit_element_module.ElementDict = dict
chainlit_step_module.StepDict = dict
chainlit_types_module.Feedback = FakeFeedback
chainlit_types_module.PageInfo = FakePageInfo
chainlit_types_module.PaginatedResponse = FakePaginatedResponse
chainlit_types_module.Pagination = FakePagination
chainlit_types_module.ThreadDict = dict
chainlit_types_module.ThreadFilter = FakeThreadFilter

sys.modules["pymongo"] = pymongo_module
sys.modules["pymongo.errors"] = pymongo_errors_module
sys.modules["chainlit"] = chainlit_module
sys.modules["chainlit.data"] = chainlit_data_module
sys.modules["chainlit.data.base"] = chainlit_data_base_module
sys.modules["chainlit.data.utils"] = chainlit_data_utils_module
sys.modules["chainlit.element"] = chainlit_element_module
sys.modules["chainlit.step"] = chainlit_step_module
sys.modules["chainlit.types"] = chainlit_types_module

spec = importlib.util.spec_from_file_location(
    "mongo_db_data_layer_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def make_layer():
    return module.MongoDBDataLayer(
        "mongodb://localhost:27017",
        "testdb",
    )


def set_find_one(layer, value):
    layer.collection.find_one = AsyncMock(return_value=value)


def set_find(layer, rows):
    layer.collection.find = Mock(return_value=FakeCursor(rows))


@pytest.fixture(autouse=True)
def reset_clients():
    FakeAsyncMongoClient.instances.clear()
    yield


def test_uses_pymongo_async_not_motor():
    source = MODULE_PATH.read_text()

    assert "from pymongo import" in source
    assert "AsyncMongoClient" in source
    assert "motor.motor_asyncio" not in source


def test_motor_import_is_removed():
    source = MODULE_PATH.read_text()

    assert "AsyncIOMotorClient" not in source


def test_constructor_validates_connection_string():
    with pytest.raises(ValueError):
        module.MongoDBDataLayer("", "db")


def test_constructor_validates_database():
    with pytest.raises(ValueError):
        module.MongoDBDataLayer("mongodb://localhost", "")


def test_constructor_validates_collection():
    with pytest.raises(ValueError):
        module.MongoDBDataLayer("mongodb://localhost", "db", "")


def test_constructor_uses_async_mongo_client():
    layer = make_layer()

    client = FakeAsyncMongoClient.instances[-1]

    assert client.connection_string == "mongodb://localhost:27017"
    assert client.kwargs["maxPoolSize"] == 100
    assert client.kwargs["serverSelectionTimeoutMS"] == 5000
    assert layer.db is not None
    assert layer.collection is not None


def test_initialize_indexes_creates_required_indexes():
    layer = make_layer()

    import asyncio

    asyncio.run(layer.initialize_indexes())

    layer.collection.create_indexes.assert_awaited_once()
    indexes = layer.collection.create_indexes.await_args.args[0]
    names = {item["name"] for item in indexes}

    assert "user_identifier_unique" in names
    assert "active_thread_listing" in names
    assert "thread_children" in names
    assert "feedback_step_unique" in names
    assert "favorite_steps" in names


def test_message_step_types_are_real_iterable_set():
    layer = make_layer()

    assert "user_message" in layer.MESSAGE_STEP_TYPES
    assert "assistant_message" in layer.MESSAGE_STEP_TYPES
    assert "system_message" in layer.MESSAGE_STEP_TYPES


def test_timestamp_is_utc_and_iso8601():
    timestamp = module.MongoDBDataLayer._timestamp()

    assert timestamp.endswith("Z")
    assert "T" in timestamp


def test_format_document_does_not_mutate_original():
    original = {"_id": "abc", "name": "thread"}

    result = module.MongoDBDataLayer._format_document(original)

    assert original == {"_id": "abc", "name": "thread"}
    assert result == {"id": "abc", "name": "thread"}


def test_format_document_handles_none():
    assert module.MongoDBDataLayer._format_document(None) is None


def test_get_user_returns_none_when_missing():
    layer = make_layer()
    set_find_one(layer, None)

    import asyncio

    assert asyncio.run(layer.get_user("user@example.com")) is None


def test_get_user_returns_persisted_user():
    layer = make_layer()
    set_find_one(
        layer,
        {
            "_id": "u1",
            "identifier": "user@example.com",
            "displayName": "Aditya",
            "createdAt": "2026-01-01T00:00:00Z",
            "metadata": {"groups": ["admin"]},
        },
    )

    import asyncio

    user = asyncio.run(layer.get_user("user@example.com"))

    assert user.id == "u1"
    assert user.identifier == "user@example.com"
    assert user.display_name == "Aditya"


def test_get_user_does_not_store_mutable_global_user_state():
    source = MODULE_PATH.read_text()

    assert "self.user_id =" not in source
    assert "self.user_identity =" not in source


def test_create_user_rejects_none_identifier():
    layer = make_layer()

    import asyncio

    with pytest.raises(ValueError):
        asyncio.run(layer.create_user(FakeUser(None)))


def test_create_user_inserts_new_user():
    layer = make_layer()

    import asyncio

    result = asyncio.run(
        layer.create_user(
            FakeUser(
                "user@example.com",
                {"claims": {"displayName": "Aditya"}},
            )
        )
    )

    layer.collection.insert_one.assert_awaited_once()
    document = layer.collection.insert_one.await_args.args[0]

    assert document["identifier"] == "user@example.com"
    assert result.identifier == "user@example.com"


def test_create_user_handles_duplicate_race():
    layer = make_layer()
    layer.collection.insert_one = AsyncMock(
        side_effect=FakeDuplicateKeyError()
    )
    layer.collection.find_one = AsyncMock(
        return_value={
            "_id": "existing",
            "identifier": "user@example.com",
            "displayName": "Existing",
            "createdAt": "2026-01-01T00:00:00Z",
            "metadata": {},
        }
    )

    import asyncio

    result = asyncio.run(
        layer.create_user(
            FakeUser("user@example.com", {"groups": ["analyst"]})
        )
    )

    assert result.id == "existing"
    layer.collection.update_one.assert_awaited_once()


def test_create_user_updates_groups_without_destroying_other_metadata():
    layer = make_layer()
    layer.collection.insert_one = AsyncMock(
        side_effect=FakeDuplicateKeyError()
    )
    layer.collection.find_one = AsyncMock(
        return_value={
            "_id": "existing",
            "identifier": "user@example.com",
            "displayName": "Existing",
            "createdAt": "old",
            "metadata": {"department": "investment"},
        }
    )

    import asyncio

    asyncio.run(
        layer.create_user(
            FakeUser(
                "user@example.com",
                {"groups": ["analyst"]},
            )
        )
    )

    update = layer.collection.update_one.await_args.args[1]
    assert update["$set"]["metadata"]["department"] == "investment"
    assert update["$set"]["metadata"]["groups"] == ["analyst"]


def test_get_feedback_queries_by_type_and_step():
    layer = make_layer()
    set_find_one(layer, {"_id": "f1", "type": "feedback", "forId": "s1"})

    import asyncio

    result = asyncio.run(layer.get_feedback("s1"))

    assert result["id"] == "f1"


def test_upsert_feedback_uses_explicit_id():
    layer = make_layer()
    set_find_one(layer, {"_id": "thread-1", "userId": "user-1"})

    import asyncio

    result = asyncio.run(
        layer.upsert_feedback(
            FakeFeedback(id="feedback-1")
        )
    )

    assert result == "feedback-1"
    layer.collection.update_one.assert_awaited_once()


def test_upsert_feedback_derives_user_from_thread():
    layer = make_layer()
    set_find_one(layer, {"_id": "thread-1", "userId": "user-1"})

    import asyncio

    asyncio.run(layer.upsert_feedback(FakeFeedback()))

    update = layer.collection.update_one.await_args.args[1]
    assert update["$set"]["userId"] == "user-1"


def test_delete_feedback_returns_boolean():
    layer = make_layer()
    layer.collection.delete_one = AsyncMock(
        return_value=types.SimpleNamespace(deleted_count=1)
    )

    import asyncio

    assert asyncio.run(layer.delete_feedback("f1")) is True


def test_create_step_is_idempotent():
    layer = make_layer()

    import asyncio

    asyncio.run(
        layer.create_step(
            {"id": "step-1", "threadId": "thread-1", "type": "user_message"}
        )
    )

    layer.collection.replace_one.assert_awaited_once()


def test_update_step_requires_id():
    layer = make_layer()

    import asyncio

    with pytest.raises(ValueError):
        asyncio.run(layer.update_step({"threadId": "t"}))


def test_delete_step_returns_boolean():
    layer = make_layer()
    layer.collection.delete_one = AsyncMock(
        return_value=types.SimpleNamespace(deleted_count=1)
    )

    import asyncio

    assert asyncio.run(layer.delete_step("step-1")) is True


def test_create_element_supports_to_dict():
    layer = make_layer()

    import asyncio

    asyncio.run(
        layer.create_element(
            FakeElement(
                {
                    "id": "element-1",
                    "threadId": "thread-1",
                    "type": "image",
                }
            )
        )
    )

    layer.collection.replace_one.assert_awaited_once()


def test_get_element_filters_by_thread():
    layer = make_layer()
    set_find_one(
        layer,
        {
            "_id": "element-1",
            "threadId": "thread-1",
            "type": "image",
        },
    )

    import asyncio

    result = asyncio.run(layer.get_element("thread-1", "element-1"))

    assert result["id"] == "element-1"
    layer.collection.find_one.assert_awaited_once_with(
        {"_id": "element-1", "threadId": "thread-1"}
    )


def test_delete_element_returns_boolean():
    layer = make_layer()
    layer.collection.delete_one = AsyncMock(
        return_value=types.SimpleNamespace(deleted_count=1)
    )

    import asyncio

    assert asyncio.run(layer.delete_element("element-1")) is True


def test_get_thread_returns_none_when_missing():
    layer = make_layer()
    set_find_one(layer, None)

    import asyncio

    assert asyncio.run(layer.get_thread("thread-1")) is None


def test_get_thread_returns_steps_and_elements():
    layer = make_layer()
    layer.collection.find_one = AsyncMock(
        return_value={
            "_id": "thread-1",
            "type": "thread",
            "isActive": True,
            "userId": "user-1",
        }
    )
    thread_cursor = FakeCursor(
        [
            {
                "_id": "step-1",
                "threadId": "thread-1",
                "type": "user_message",
                "createdAt": "2026-01-01T00:00:01Z",
            },
            {
                "_id": "element-1",
                "threadId": "thread-1",
                "type": "image",
                "createdAt": "2026-01-01T00:00:02Z",
            },
        ]
    )
    feedback_cursor = FakeCursor([])
    layer.collection.find = Mock(side_effect=[thread_cursor, feedback_cursor])

    import asyncio

    result = asyncio.run(layer.get_thread("thread-1"))

    assert result["id"] == "thread-1"
    assert len(result["steps"]) == 1
    assert len(result["elements"]) == 1


def test_get_thread_does_not_include_inactive_thread():
    layer = make_layer()
    set_find_one(
        layer,
        {
            "_id": "thread-1",
            "type": "thread",
            "isActive": False,
        },
    )

    import asyncio

    assert asyncio.run(layer.get_thread("thread-1")) is None


def test_get_thread_loads_feedback_in_batch():
    layer = make_layer()
    layer.collection.find_one = AsyncMock(
        return_value={
            "_id": "thread-1",
            "type": "thread",
            "isActive": True,
        }
    )

    thread_cursor = FakeCursor(
        [
            {
                "_id": "step-1",
                "threadId": "thread-1",
                "type": "user_message",
            },
            {
                "_id": "step-2",
                "threadId": "thread-1",
                "type": "assistant_message",
            },
        ]
    )
    feedback_cursor = FakeCursor(
        [
            {
                "_id": "feedback-1",
                "type": "feedback",
                "forId": "step-1",
            }
        ]
    )

    layer.collection.find = Mock(
        side_effect=[thread_cursor, feedback_cursor]
    )

    import asyncio

    result = asyncio.run(layer.get_thread("thread-1"))

    assert result["steps"][0]["feedback"]["id"] == "feedback-1"
    assert result["steps"][1]["feedback"] is None


def test_get_thread_author_reads_persisted_thread():
    layer = make_layer()
    set_find_one(
        layer,
        {
            "_id": "thread-1",
            "type": "thread",
            "userIdentifier": "user@example.com",
        },
    )

    import asyncio

    assert asyncio.run(layer.get_thread_author("thread-1")) == "user@example.com"


def test_update_thread_preserves_empty_values():
    layer = make_layer()
    layer.collection.find_one = AsyncMock(return_value=None)

    import asyncio

    asyncio.run(
        layer.update_thread(
            "thread-1",
            name="",
            user_id="user-1",
            metadata={},
            tags=[],
        )
    )

    update = layer.collection.update_one.await_args.args[1]["$set"]

    assert update["name"] == ""
    assert update["metadata"] == {}
    assert update["tags"] == []


def test_update_thread_sets_user_identifier_from_user():
    layer = make_layer()

    layer.collection.find_one = AsyncMock(
        return_value={
            "_id": "user-1",
            "type": "user",
            "identifier": "user@example.com",
        }
    )

    import asyncio

    asyncio.run(
        layer.update_thread(
            "thread-1",
            user_id="user-1",
        )
    )

    update = layer.collection.update_one.await_args.args[1]["$set"]
    assert update["userIdentifier"] == "user@example.com"


def test_delete_thread_is_soft_delete():
    layer = make_layer()

    import asyncio

    asyncio.run(layer.delete_thread("thread-1"))

    update = layer.collection.update_one.await_args.args[1]
    assert update["$set"]["isActive"] is False


def test_list_threads_uses_user_filter():
    layer = make_layer()
    rows = [
        {
            "_id": "t1",
            "type": "thread",
            "isActive": True,
            "userId": "u1",
            "createdAt": "2026-01-02T00:00:00Z",
        }
    ]
    set_find(layer, rows)

    import asyncio

    result = asyncio.run(
        layer.list_threads(
            FakePagination(first=10),
            FakeThreadFilter(userId="u1"),
        )
    )

    query = layer.collection.find.call_args.args[0]
    assert query["userId"] == "u1"
    assert len(result.data) == 1


def test_list_threads_escapes_regex_input():
    layer = make_layer()
    set_find(layer, [])

    import asyncio

    asyncio.run(
        layer.list_threads(
            FakePagination(first=10),
            FakeThreadFilter(search="a.b"),
        )
    )

    query = layer.collection.find.call_args.args[0]
    assert query["name"]["$regex"] == r"a\.b"


def test_list_threads_uses_limit_plus_one():
    layer = make_layer()
    set_find(
        layer,
        [
            {
                "_id": "t1",
                "type": "thread",
                "createdAt": "2026-01-02T00:00:00Z",
            },
            {
                "_id": "t2",
                "type": "thread",
                "createdAt": "2026-01-01T00:00:00Z",
            },
        ],
    )

    import asyncio

    result = asyncio.run(
        layer.list_threads(
            FakePagination(first=1),
            FakeThreadFilter(),
        )
    )

    cursor = layer.collection.find.return_value
    assert cursor.limit_value == 2
    assert result.pageInfo.hasNextPage is True


def test_list_threads_returns_opaque_cursors():
    layer = make_layer()
    set_find(
        layer,
        [
            {
                "_id": "t1",
                "type": "thread",
                "createdAt": "2026-01-02T00:00:00Z",
            }
        ],
    )

    import asyncio

    result = asyncio.run(
        layer.list_threads(
            FakePagination(first=10),
            FakeThreadFilter(),
        )
    )

    assert result.pageInfo.startCursor
    assert result.pageInfo.endCursor


def test_cursor_round_trip():
    cursor = module.MongoDBDataLayer._encode_cursor(
        "2026-01-01T00:00:00Z",
        "thread-1",
    )

    decoded = module.MongoDBDataLayer._decode_cursor(cursor)

    assert decoded == {
        "createdAt": "2026-01-01T00:00:00Z",
        "id": "thread-1",
    }


def test_invalid_cursor_is_rejected():
    with pytest.raises(ValueError, match="Invalid pagination cursor"):
        module.MongoDBDataLayer._decode_cursor("not-a-valid-cursor")


def test_delete_user_session_returns_boolean():
    layer = make_layer()
    layer.collection.delete_one = AsyncMock(
        return_value=types.SimpleNamespace(deleted_count=1)
    )

    import asyncio

    assert asyncio.run(layer.delete_user_session("session-1")) is True


def test_get_favorite_steps_filters_user_and_favorite_metadata():
    layer = make_layer()
    set_find(
        layer,
        [
            {
                "_id": "step-1",
                "type": "assistant_message",
                "userId": "user-1",
                "metadata": {"favorited": True},
            }
        ],
    )

    import asyncio

    result = asyncio.run(layer.get_favorite_steps("user-1"))

    query = layer.collection.find.call_args.args[0]
    assert query["userId"] == "user-1"
    assert query["metadata.favorited"] is True
    assert result[0]["id"] == "step-1"


def test_close_closes_async_client():
    layer = make_layer()

    import asyncio

    asyncio.run(layer.close())

    assert FakeAsyncMongoClient.instances[-1].closed is True


def test_required_current_chainlit_methods_are_implemented():
    required = [
        "get_user",
        "create_user",
        "upsert_feedback",
        "delete_feedback",
        "create_element",
        "get_element",
        "delete_element",
        "create_step",
        "update_step",
        "delete_step",
        "get_thread_author",
        "delete_thread",
        "list_threads",
        "get_thread",
        "update_thread",
        "delete_user_session",
        "get_favorite_steps",
        "close",
    ]

    for name in required:
        assert hasattr(module.MongoDBDataLayer, name)
        assert callable(getattr(module.MongoDBDataLayer, name))


def test_no_mutable_request_user_state():
    source = MODULE_PATH.read_text()

    assert "self.user_identity" not in source
    assert "self.user_id" not in source


def test_no_motor_import_dependency():
    source = MODULE_PATH.read_text()

    assert "motor.motor_asyncio" not in source
    assert "AsyncIOMotorClient" not in source


def test_no_unbounded_get_thread_read():
    source = MODULE_PATH.read_text()

    assert "to_list(length=1000)" not in source


def test_thread_listing_has_tie_breaker():
    source = MODULE_PATH.read_text()

    assert '("_id", DESCENDING)' in source


def test_search_input_is_escaped():
    source = MODULE_PATH.read_text()

    assert "re.escape(filters.search)" in source


def test_client_close_is_present():
    source = MODULE_PATH.read_text()

    assert "async def close" in source
    assert "await self.client.close()" in source


def test_current_driver_import_is_async_client():
    source = MODULE_PATH.read_text()

    assert "from pymongo import ASCENDING, DESCENDING, AsyncMongoClient" in source


def test_uuid_ids_remain_string_compatible():
    source = MODULE_PATH.read_text()

    assert 'str(__import__("uuid").uuid4())' in source


def test_thread_soft_delete_is_explicit():
    source = MODULE_PATH.read_text()

    assert '"isActive": False' in source


def test_source_does_not_use_skip_zero():
    source = MODULE_PATH.read_text()

    assert ".skip(0)" not in source


def test_source_does_not_mutate_mongo_documents_during_formatting():
    source = MODULE_PATH.read_text()

    assert "doc.pop(\"_id\")" not in source
