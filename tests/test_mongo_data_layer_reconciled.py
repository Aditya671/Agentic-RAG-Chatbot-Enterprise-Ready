import asyncio

from backend.databases.mongo_db_data_layer import MongoDBDataLayer


class AsyncCursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, *_args, **_kwargs):
        return self

    def skip(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return self.rows[:length] if length else list(self.rows)


class FakeCollection:
    def __init__(self):
        self.rows = []
        self.index_calls = []

    async def create_indexes(self, indexes):
        self.index_calls.append(indexes)

    async def find_one(self, query):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return dict(row)
        return None

    async def insert_one(self, document):
        self.rows.append(dict(document))

    async def update_one(self, query, update, upsert=False):
        target = next((row for row in self.rows if all(row.get(k) == v for k, v in query.items())), None)
        if target is None:
            if upsert:
                target = dict(query)
                self.rows.append(target)
            else:
                return type("Result", (), {"modified_count": 0, "deleted_count": 0})()
        target.update(update.get("$set", {}))
        target.update(update.get("$setOnInsert", {}))
        return type("Result", (), {"modified_count": 1, "deleted_count": 0})()

    async def delete_one(self, query):
        before = len(self.rows)
        self.rows = [row for row in self.rows if not all(row.get(k) == v for k, v in query.items())]
        return type("Result", (), {"deleted_count": int(len(self.rows) != before)})()

    def find(self, query):
        rows = []
        for row in self.rows:
            match = True
            for key, value in query.items():
                if isinstance(value, dict) and "$regex" in value:
                    if value["$regex"].lower() not in str(row.get(key, "")).lower():
                        match = False
                elif row.get(key) != value:
                    match = False
            if match:
                rows.append(dict(row))
        return AsyncCursor(rows)


class FakeDatabase:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, _):
        return self.collection


class FakeClient:
    def __init__(self, collection):
        self.collection = collection
        self.closed = False

    def __getitem__(self, _):
        return FakeDatabase(self.collection)

    async def close(self):
        self.closed = True


def make_layer(monkeypatch):
    collection = FakeCollection()
    client = FakeClient(collection)
    monkeypatch.setattr(
        "backend.databases.mongo_db_data_layer.AsyncMongoClient",
        lambda *args, **kwargs: client,
    )
    layer = MongoDBDataLayer("mongodb://example", "db")
    return layer, collection, client


def test_constructor_validates_connection_settings(monkeypatch):
    for value in ("", " "):
        try:
            MongoDBDataLayer(value, "db")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid connection string should be rejected")


def test_user_round_trip(monkeypatch):
    layer, collection, _ = make_layer(monkeypatch)
    user = type("User", (), {"identifier": "alice", "display_name": "Alice", "metadata": {}})()

    persisted = asyncio.run(layer.create_user(user))
    loaded = asyncio.run(layer.get_user("alice"))

    assert persisted.identifier == "alice"
    assert loaded.identifier == "alice"
    assert collection.rows[0]["type"] == "user"


def test_step_and_thread_round_trip(monkeypatch):
    layer, collection, _ = make_layer(monkeypatch)
    asyncio.run(layer.update_thread("thread-1", name="Test"))
    asyncio.run(layer.create_step({"id": "step-1", "threadId": "thread-1", "type": "user_message", "createdAt": "2026-01-01T00:00:00Z"}))

    thread = asyncio.run(layer.get_thread("thread-1"))

    assert thread["id"] == "thread-1"
    assert [step["id"] for step in thread["steps"]] == ["step-1"]
    assert any(row.get("threadId") == "thread-1" for row in collection.rows)


def test_initialize_indexes_and_close(monkeypatch):
    layer, collection, client = make_layer(monkeypatch)

    asyncio.run(layer.initialize_indexes())
    asyncio.run(layer.close())

    assert collection.index_calls
    assert client.closed is True
