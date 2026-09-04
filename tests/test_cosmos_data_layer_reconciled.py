import asyncio

from backend.databases.cosmos_db_date_layer import CosmosDBDataLayer


class FakeContainer:
    def __init__(self, items=None):
        self.items = [dict(item) for item in (items or [])]
        self.queries = []
        self.upserts = []
        self.deletes = []

    def query_items(self, query, parameters=None, **kwargs):
        self.queries.append((query, parameters or [], kwargs))
        values = {item["name"]: item["value"] for item in parameters or []}
        rows = list(self.items)
        if values.get("@type") is not None:
            rows = [row for row in rows if row.get("type") == values["@type"]]
        if values.get("@identifier") is not None:
            rows = [row for row in rows if row.get("identifier") == values["@identifier"]]
        if values.get("@id") is not None:
            rows = [row for row in rows if row.get("id") == values["@id"]]
        if values.get("@threadId") is not None:
            rows = [
                row for row in rows
                if row.get("threadId") == values["@threadId"] or row.get("id") == values["@threadId"]
            ]
        if values.get("@threadType") == "thread":
            rows = [row for row in rows if row.get("type") == "thread" and row.get("isActive", True)]
        if "partition_key" in kwargs:
            rows = [row for row in rows if row.get("partition_thread_id") == kwargs["partition_key"]]
        return iter(rows[: kwargs.get("max_item_count", len(rows))])

    def upsert_item(self, body):
        self.upserts.append(dict(body))
        self.items = [row for row in self.items if row.get("id") != body.get("id")]
        self.items.append(dict(body))

    def create_item(self, body):
        self.upserts.append(dict(body))
        self.items.append(dict(body))

    def delete_item(self, item, partition_key):
        self.deletes.append((item, partition_key))
        self.items = [row for row in self.items if row.get("id") != item]


class FakeDatabase:
    def __init__(self, container):
        self.container = container

    def get_container_client(self, _):
        return self.container


class FakeClient:
    def __init__(self, container):
        self.container = container
        self.closed = False

    def get_database_client(self, _):
        return FakeDatabase(self.container)

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


def test_user_lookup_is_parameterized_and_partition_safe():
    layer, container, _ = make_layer([
        {
            "id": "u1", "type": "user", "identifier": "alice",
            "displayName": "Alice", "metadata": {},
            "partition_thread_id": "u1",
        }
    ])

    user = asyncio.run(layer.get_user("alice"))

    assert user.identifier == "alice"
    query, parameters, kwargs = container.queries[-1]
    assert "@identifier" in query
    assert "alice" not in query
    assert kwargs["enable_cross_partition_query"] is True
    assert {p["name"] for p in parameters} == {"@type", "@identifier"}


def test_step_persistence_sets_partition_key_and_ttl():
    layer, container, _ = make_layer()

    asyncio.run(layer.create_step({"id": "s1", "threadId": "t1", "type": "step"}))

    stored = container.upserts[-1]
    assert stored["partition_thread_id"] == "t1"
    assert stored["ttl"] == 2_592_000


def test_thread_retrieval_is_partition_scoped():
    layer, container, _ = make_layer([
        {"id": "t1", "type": "thread", "isActive": True, "partition_thread_id": "t1"},
        {"id": "s2", "type": "step", "threadId": "t1", "createdAt": "2026-01-02", "partition_thread_id": "t1"},
        {"id": "s1", "type": "step", "threadId": "t1", "createdAt": "2026-01-01", "partition_thread_id": "t1"},
    ])

    thread = asyncio.run(layer.get_thread("t1"))

    assert [step["id"] for step in thread["steps"]] == ["s1", "s2"]
    assert any(kwargs.get("partition_key") == "t1" for _, _, kwargs in container.queries)


def test_close_is_idempotent():
    layer, _, client = make_layer()

    asyncio.run(layer.close())
    asyncio.run(layer.close())

    assert client.closed is True
