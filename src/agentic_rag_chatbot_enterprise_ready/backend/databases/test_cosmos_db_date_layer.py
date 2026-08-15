import asyncio
import importlib.util
import sys
import types
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path("/mnt/data/cosmos_db_date_layer_upgraded.py")


def install_dependency_stubs():
    # Azure Cosmos
    azure = types.ModuleType("azure")
    cosmos = types.ModuleType("azure.cosmos")

    class FakeCosmosClient:
        def __init__(self, *args, **kwargs):
            self.closed = False

        def get_database_client(self, name):
            return types.SimpleNamespace(
                get_container_client=lambda container: None
            )

        def close(self):
            self.closed = True

    cosmos.CosmosClient = FakeCosmosClient
    azure.cosmos = cosmos

    # Chainlit
    chainlit = types.ModuleType("chainlit")

    class User:
        def __init__(self, identifier="u1", display_name="User", metadata=None):
            self.identifier = identifier
            self.display_name = display_name
            self.metadata = metadata or {}

    class PersistedUser:
        def __init__(self, id, display_name, identifier, createdAt=None, metadata=None):
            self.id = id
            self.display_name = display_name
            self.identifier = identifier
            self.createdAt = createdAt
            self.metadata = metadata or {}

    chainlit.User = User
    chainlit.PersistedUser = PersistedUser

    data = types.ModuleType("chainlit.data")

    class BaseDataLayer:
        pass

    data.BaseDataLayer = BaseDataLayer

    def queue_until_user_message():
        def decorator(fn):
            return fn
        return decorator

    data.queue_until_user_message = queue_until_user_message

    user_module = types.ModuleType("chainlit.user")
    user_module.User = User
    user_module.PersistedUser = PersistedUser

    element = types.ModuleType("chainlit.element")
    element.ElementDict = dict

    step = types.ModuleType("chainlit.step")
    step.StepDict = dict

    types_mod = types.ModuleType("chainlit.types")

    class Feedback:
        def __init__(self, id=None, forId=None, value=0, comment=None, threadId=None):
            self.id = id
            self.forId = forId
            self.value = value
            self.comment = comment
            self.threadId = threadId

        def __iter__(self):
            return iter(
                {
                    "id": self.id,
                    "forId": self.forId,
                    "value": self.value,
                    "comment": self.comment,
                    "threadId": self.threadId,
                }.items()
            )

    class PageInfo:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class PaginatedResponse:
        def __init__(self, data, pageInfo):
            self.data = data
            self.pageInfo = pageInfo

    class Pagination:
        def __init__(self, first=20, cursor=None):
            self.first = first
            self.cursor = cursor

    class ThreadFilter:
        def __init__(self, userId=None, search=None):
            self.userId = userId
            self.search = search

    types_mod.Feedback = Feedback
    types_mod.PageInfo = PageInfo
    types_mod.PaginatedResponse = PaginatedResponse
    types_mod.Pagination = Pagination
    types_mod.ThreadDict = dict
    types_mod.ThreadFilter = ThreadFilter

    sys.modules.update(
        {
            "azure": azure,
            "azure.cosmos": cosmos,
            "chainlit": chainlit,
            "chainlit.data": data,
            "chainlit.user": user_module,
            "chainlit.element": element,
            "chainlit.step": step,
            "chainlit.types": types_mod,
        }
    )


install_dependency_stubs()
spec = importlib.util.spec_from_file_location("cosmos_layer_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

CosmosDBDataLayer = module.CosmosDBDataLayer
TTL_30_DAYS = module.TTL_30_DAYS


class FakeContainer:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.upserts = []
        self.creates = []
        self.deletes = []
        self.queries = []

    def upsert_item(self, body):
        self.upserts.append(body)
        self._replace(body)

    def create_item(self, body):
        self.creates.append(body)
        self._replace(body)

    def _replace(self, body):
        self.items = [x for x in self.items if x.get("id") != body.get("id")]
        self.items.append(dict(body))

    def delete_item(self, item, partition_key):
        self.deletes.append((item, partition_key))
        self.items = [x for x in self.items if x.get("id") != item]

    def query_items(self, query, parameters=None, **kwargs):
        self.queries.append(
            {"query": query, "parameters": parameters or [], "kwargs": kwargs}
        )
        values = {p["name"]: p["value"] for p in parameters or []}
        result = list(self.items)

        if values.get("@type") == "user":
            result = [x for x in result if x.get("type") == "user"]
        if "@identifier" in values:
            result = [x for x in result if x.get("identifier") == values["@identifier"]]
        if values.get("@id") is not None:
            result = [x for x in result if x.get("id") == values["@id"]]
        if values.get("@threadId") is not None:
            tid = values["@threadId"]
            result = [
                x for x in result
                if x.get("threadId") == tid or x.get("id") == tid
            ]
        if values.get("@userId") is not None:
            result = [x for x in result if x.get("userId") == values["@userId"]]
        if values.get("@search") is not None:
            s = values["@search"].lower()
            result = [x for x in result if s in str(x.get("name", "")).lower()]
        if values.get("@threadType") == "thread" and "@threadId" not in values:
            result = [x for x in result if x.get("type") == "thread" and x.get("isActive") is True]

        pk = kwargs.get("partition_key")
        if pk is not None:
            result = [
                x for x in result
                if x.get("partition_thread_id") == pk
            ]

        return iter(result)


class FakeDB:
    def __init__(self, container):
        self.container = container

    def get_container_client(self, name):
        return self.container


class FakeClient:
    def __init__(self, container):
        self.container = container
        self.closed = False

    def get_database_client(self, name):
        return FakeDB(self.container)

    def close(self):
        self.closed = True


def make_layer(items=None):
    container = FakeContainer(items)
    client = FakeClient(container)
    layer = CosmosDBDataLayer(
        credential=object(),
        url="https://example.documents.azure.com:443/",
        database_id="db",
        container_id="container",
        client=client,
    )
    return layer, container, client


def test_prepare_item_does_not_mutate_input():
    layer, _, _ = make_layer()
    original = {"id": "x", "threadId": "t"}
    result = layer._prepare_item(original)

    assert original == {"id": "x", "threadId": "t"}
    assert result["partition_thread_id"] == "t"


def test_prepare_item_requires_id_or_thread_id():
    layer, _, _ = make_layer()

    try:
        layer._prepare_item({"type": "step"})
        assert False
    except ValueError:
        assert True


def test_parameterized_query_is_used_for_user_lookup():
    layer, container, _ = make_layer(
        [
            {
                "id": "u1",
                "type": "user",
                "identifier": "alice",
                "displayName": "Alice",
                "metadata": {},
                "createdAt": "2026-01-01T00:00:00+00:00",
                "partition_thread_id": "u1",
            }
        ]
    )

    user = asyncio.run(layer.get_user("alice"))

    assert user.identifier == "alice"
    assert "@identifier" in container.queries[-1]["query"]
    assert "alice" not in container.queries[-1]["query"]


def test_create_user_updates_existing_user_without_isinstance_bug():
    layer, container, _ = make_layer(
        [
            {
                "id": "u1",
                "type": "user",
                "identifier": "alice",
                "displayName": "Alice",
                "metadata": {"old": True},
                "createdAt": "2026-01-01T00:00:00+00:00",
                "partition_thread_id": "u1",
            }
        ]
    )

    User = sys.modules["chainlit"].User
    user = User(
        identifier="alice",
        display_name="Alice Updated",
        metadata={"groups": ["g1"]},
    )

    persisted = asyncio.run(layer.create_user(user))

    assert persisted.id == "u1"
    assert persisted.metadata["old"] is True
    assert persisted.metadata["groups"] == ["g1"]
    assert container.upserts[-1]["updatedAt"] != container.upserts[-1]["createdAt"]


def test_create_step_sets_partition_and_ttl():
    layer, container, _ = make_layer()

    asyncio.run(
        layer.create_step(
            {
                "id": "s1",
                "threadId": "t1",
                "type": "step",
            }
        )
    )

    stored = container.upserts[-1]
    assert stored["partition_thread_id"] == "t1"
    assert stored["ttl"] == TTL_30_DAYS


def test_update_step_requires_id():
    layer, _, _ = make_layer()

    try:
        asyncio.run(layer.update_step({"threadId": "t1"}))
        assert False
    except ValueError:
        assert True


def test_get_thread_is_partition_scoped_and_builds_steps():
    layer, container, _ = make_layer(
        [
            {
                "id": "t1",
                "type": "thread",
                "isActive": True,
                "createdAt": "2026-01-01T00:00:00+00:00",
                "partition_thread_id": "t1",
            },
            {
                "id": "s2",
                "type": "step",
                "threadId": "t1",
                "createdAt": "2026-01-02T00:00:00+00:00",
                "partition_thread_id": "t1",
            },
            {
                "id": "s1",
                "type": "step",
                "threadId": "t1",
                "createdAt": "2026-01-01T00:00:00+00:00",
                "partition_thread_id": "t1",
            },
        ]
    )

    thread = asyncio.run(layer.get_thread("t1"))

    assert [s["id"] for s in thread["steps"]] == ["s1", "s2"]
    assert any(
        q["kwargs"].get("partition_key") == "t1"
        for q in container.queries
    )


def test_update_thread_creates_partitioned_thread():
    layer, container, _ = make_layer()

    asyncio.run(layer.update_thread("t1", name="Test"))

    stored = container.upserts[-1]
    assert stored["id"] == "t1"
    assert stored["partition_thread_id"] == "t1"
    assert stored["name"] == "Test"


def test_hard_delete_thread_deletes_partition_items():
    layer, container, _ = make_layer(
        [
            {"id": "t1", "type": "thread", "partition_thread_id": "t1"},
            {"id": "s1", "type": "step", "threadId": "t1", "partition_thread_id": "t1"},
        ]
    )

    assert asyncio.run(layer.hard_delete_thread("t1")) is True
    assert {x[0] for x in container.deletes} == {"t1", "s1"}


def test_list_threads_respects_page_size_and_parameters():
    layer, container, _ = make_layer(
        [
            {
                "id": "t1",
                "type": "thread",
                "isActive": True,
                "userId": "u1",
                "name": "Alpha",
                "createdAt": "2026-01-01",
                "partition_thread_id": "t1",
            }
        ]
    )

    Pagination = sys.modules["chainlit.types"].Pagination
    ThreadFilter = sys.modules["chainlit.types"].ThreadFilter

    response = asyncio.run(
        layer.list_threads(
            Pagination(first=10),
            ThreadFilter(userId="u1", search="Al"),
        )
    )

    assert len(response.data) == 1
    assert container.queries[-1]["kwargs"]["max_item_count"] == 10
    assert "@userId" in container.queries[-1]["query"]
    assert "@search" in container.queries[-1]["query"]


def test_delete_step_uses_partition_key_when_available():
    layer, container, _ = make_layer()

    assert asyncio.run(layer.delete_step("s1", thread_id="t1")) is True
    assert container.deletes == [("s1", "t1")]


def test_delete_element_supports_current_and_legacy_signature():
    layer, container, _ = make_layer()

    assert asyncio.run(layer.delete_element("e1", "t1")) is True
    assert container.deletes[-1] == ("e1", "t1")


def test_get_favorite_steps_returns_empty_when_none():
    layer, _, _ = make_layer()
    assert asyncio.run(layer.get_favorite_steps("u1")) == []


def test_close_is_idempotent():
    layer, _, client = make_layer()

    asyncio.run(layer.close())
    asyncio.run(layer.close())

    assert client.closed is True


def test_timestamp_is_timezone_aware():
    value = module.CosmosDBDataLayer._timestamp()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
