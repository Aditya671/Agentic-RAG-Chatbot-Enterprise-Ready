from __future__ import annotations

import asyncio
import datetime as dt
import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from azure.cosmos import CosmosClient
from chainlit.data import BaseDataLayer, queue_until_user_message
from chainlit.user import PersistedUser, User
from chainlit.element import ElementDict
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)

logger = logging.getLogger(__name__)

TTL_30_DAYS = 2_592_000


class CosmosDBDataLayer(BaseDataLayer):
    """Chainlit data layer backed by Azure Cosmos DB SQL API.

    The implementation intentionally keeps the existing container schema and
    partition-key field (``partition_thread_id``) for compatibility.

    Design rules:
    - All blocking Cosmos SDK calls are isolated with ``asyncio.to_thread``.
    - Cosmos SQL values are supplied through parameters, never interpolated.
    - Thread-scoped reads/deletes use the known partition key whenever possible.
    - Chainlit's current ``BaseDataLayer`` contract is implemented, including
      ``get_favorite_steps`` and ``close``.
    - A synchronous CosmosClient is retained because it is compatible with the
      existing application and can be injected in tests. The blocking SDK call
      is never allowed directly on the async event loop.
    """

    message_step_types = frozenset(
        {
            "step",
            "user_message",
            "assistant_message",
            "run",
            "tool",
            "llm",
            "embedding",
            "retrieval",
            "rerank",
            "undefined",
        }
    )

    element_types = frozenset(
        {
            "image",
            "text",
            "pdf",
            "tasklist",
            "audio",
            "video",
            "file",
            "plotly",
            "dataframe",
            "custom",
        }
    )

    def __init__(
        self,
        credential: Any,
        url: str,
        database_id: str,
        container_id: str,
        partition_key_field: str = "partition_thread_id",
        *,
        client: Optional[Any] = None,
    ) -> None:
        if not url:
            raise ValueError("url must be provided.")
        if not database_id:
            raise ValueError("database_id must be provided.")
        if not container_id:
            raise ValueError("container_id must be provided.")
        if not partition_key_field:
            raise ValueError("partition_key_field must be provided.")

        # Dependency injection is intentionally supported for unit/integration tests.
        self.client = client or CosmosClient(url=url, credential=credential)
        self.db = self.client.get_database_client(database_id)
        self.container = self.db.get_container_client(container_id)

        self.partition_key_field = partition_key_field
        self.user_identity = "local_user"
        self.user_id = str(uuid.uuid4())
        self._closed = False

        # Retained as a compatibility/configuration reference. Container
        # indexing policies should be managed as infrastructure, not per request.
        self.indexing_policy = {
            "indexingMode": "consistent",
            "includedPaths": [
                {"path": "/type/?"},
                {"path": "/userId/?"},
                {"path": "/name/?"},
                {"path": "/createdAt/?"},
            ],
            "excludedPaths": [
                {"path": "/*"},
                {"path": '/"_etag"/?'},
            ],
        }

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _timestamp() -> str:
        return dt.datetime.now(dt.timezone.utc).isoformat()

    @staticmethod
    def _strip_cosmos_meta(obj: Dict[str, Any]) -> Dict[str, Any]:
        # Never mutate the object returned by the SDK.
        cleaned = dict(obj)
        for cosmos_key in ("_rid", "_self", "_etag", "_attachments", "_ts"):
            cleaned.pop(cosmos_key, None)
        return cleaned

    def _prepare_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy with the configured partition-key value populated."""
        prepared = dict(item)
        pk_value = prepared.get("threadId") or prepared.get("id")
        if pk_value is None:
            raise ValueError("Persisted item must contain either 'threadId' or 'id'.")
        prepared.setdefault(self.partition_key_field, pk_value)
        return prepared

    @staticmethod
    def _parameter(name: str, value: Any) -> Dict[str, Any]:
        return {"name": name, "value": value}

    async def _query(
        self,
        query: str,
        *,
        parameters: Optional[Sequence[Dict[str, Any]]] = None,
        partition_key: Any = None,
        cross_partition: bool = False,
        max_item_count: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a synchronous SDK query off the event loop."""
        kwargs: Dict[str, Any] = {
            "query": query,
            "parameters": list(parameters or []),
        }

        if partition_key is not None:
            kwargs["partition_key"] = partition_key
        elif cross_partition:
            kwargs["enable_cross_partition_query"] = True

        if max_item_count is not None:
            kwargs["max_item_count"] = max_item_count

        iterator = await asyncio.to_thread(
            lambda: self.container.query_items(**kwargs)
        )
        return await asyncio.to_thread(lambda: list(iterator))

    async def _upsert(self, item: Dict[str, Any]) -> Any:
        prepared = self._prepare_item(item)
        return await asyncio.to_thread(
            lambda: self.container.upsert_item(body=prepared)
        )

    async def _create(self, item: Dict[str, Any]) -> Any:
        prepared = self._prepare_item(item)
        return await asyncio.to_thread(
            lambda: self.container.create_item(body=prepared)
        )

    async def _delete_item(self, item_id: str, partition_key: Any) -> None:
        await asyncio.to_thread(
            lambda: self.container.delete_item(
                item=item_id,
                partition_key=partition_key,
            )
        )

    # ------------------------------------------------------------------
    # USER
    # ------------------------------------------------------------------

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        if not identifier:
            return None

        query = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.type = @type AND c.identifier = @identifier"
        )
        items = await self._query(
            query,
            parameters=[
                self._parameter("@type", "user"),
                self._parameter("@identifier", identifier),
            ],
            cross_partition=True,
            max_item_count=1,
        )

        if not items:
            return None

        row = items[0]
        self.user_identity = str(row.get("identifier") or "local_user")
        self.user_id = str(row.get("id"))

        return PersistedUser(
            id=str(row.get("id")),
            display_name=str(row.get("displayName") or ""),
            identifier=str(row.get("identifier") or ""),
            createdAt=row.get("createdAt"),
            metadata=row.get("metadata") or {},
        )

    async def create_user(self, user: User) -> PersistedUser:
        if not user.identifier:
            raise ValueError("Chainlit user identifier is required.")

        existing = await self.get_user(user.identifier)
        incoming_metadata = dict(user.metadata or {})

        if existing:
            self.user_identity = str(existing.identifier)
            self.user_id = str(existing.id)

            metadata = dict(existing.metadata or {})
            # Preserve existing metadata and only update claims supplied by the
            # current authentication event.
            metadata.update(incoming_metadata)

            now = self._timestamp()
            updated_item = {
                "id": str(existing.id),
                "identifier": str(existing.identifier),
                "type": "user",
                "displayName": str(
                    user.display_name
                    or metadata.get("claims", {}).get("displayName")
                    or existing.display_name
                    or ""
                ),
                "metadata": metadata,
                "createdAt": existing.createdAt or now,
                "updatedAt": now,
            }
            await self._upsert(updated_item)

            return PersistedUser(
                id=updated_item["id"],
                display_name=updated_item["displayName"],
                identifier=updated_item["identifier"],
                createdAt=updated_item["createdAt"],
                metadata=metadata,
            )

        now = self._timestamp()
        display_name = (
            user.display_name
            or incoming_metadata.get("claims", {}).get("displayName")
            or ""
        )

        new_user = {
            "id": str(uuid.uuid4()),
            "identifier": str(user.identifier),
            "type": "user",
            "displayName": display_name,
            "metadata": incoming_metadata,
            "createdAt": now,
            "updatedAt": now,
        }

        self.user_identity = new_user["identifier"]
        self.user_id = new_user["id"]
        await self._create(new_user)

        return PersistedUser(
            id=new_user["id"],
            display_name=new_user["displayName"],
            identifier=new_user["identifier"],
            createdAt=new_user["createdAt"],
            metadata=new_user["metadata"],
        )

    async def delete_user_session(self, id: str) -> bool:
        if not id:
            return False

        try:
            await self._delete_item(id, id)
            return True
        except Exception:
            logger.exception("Failed to delete user session")
            return False

    # ------------------------------------------------------------------
    # FEEDBACK
    # ------------------------------------------------------------------

    async def get_feedback(self, step_id: str) -> Optional[Dict[str, Any]]:
        query = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.type = @type AND c.forId = @forId"
        )
        items = await self._query(
            query,
            parameters=[
                self._parameter("@type", "feedback"),
                self._parameter("@forId", step_id),
            ],
            cross_partition=True,
            max_item_count=1,
        )
        return self._strip_cosmos_meta(items[0]) if items else None

    async def upsert_feedback(self, feedback: Feedback) -> str:
        existing = await self.get_feedback(feedback.forId)
        now = self._timestamp()

        if existing:
            feedback_dict = {
                **existing,
                "value": feedback.value,
                "comment": feedback.comment,
                "updatedAt": now,
            }
            feedback_id = str(existing["id"])
        else:
            feedback_id = str(feedback.id or uuid.uuid4())
            feedback_dict = {
                **dict(feedback),
                "id": feedback_id,
                "type": "feedback",
                "userId": self.user_id,
                "createdAt": now,
                "updatedAt": now,
            }

        feedback_dict.setdefault("threadId", getattr(feedback, "threadId", None))
        feedback_dict = self._prepare_item(feedback_dict)
        await self._upsert(feedback_dict)
        return feedback_id

    async def delete_feedback(self, feedback_id: str) -> bool:
        if not feedback_id:
            return False

        try:
            query = (
                "SELECT c.id, c." + self.partition_key_field + " FROM c "
                "WHERE c.type = @type AND c.id = @id"
            )
            items = await self._query(
                query,
                parameters=[
                    self._parameter("@type", "feedback"),
                    self._parameter("@id", feedback_id),
                ],
                cross_partition=True,
                max_item_count=10,
            )
            for item in items:
                await self._delete_item(
                    item["id"],
                    item[self.partition_key_field],
                )
            return bool(items)
        except Exception:
            logger.exception("Failed to delete feedback")
            return False

    # ------------------------------------------------------------------
    # ELEMENTS
    # ------------------------------------------------------------------

    @queue_until_user_message()
    async def create_element(self, element_dict: ElementDict) -> None:
        element = element_dict.to_dict()
        element.setdefault("type", "element")
        element.setdefault("createdAt", self._timestamp())
        await self._upsert(element)

    @queue_until_user_message()
    async def get_element(
        self,
        thread_id: str,
        element_id: str,
    ) -> Optional[ElementDict]:
        query = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.threadId = @threadId AND c.id = @id"
        )
        items = await self._query(
            query,
            parameters=[
                self._parameter("@threadId", thread_id),
                self._parameter("@id", element_id),
            ],
            partition_key=thread_id,
            max_item_count=1,
        )
        return self._strip_cosmos_meta(items[0]) if items else None

    @queue_until_user_message()
    async def delete_element(
        self,
        element_id: str,
        thread_id: Optional[str] = None,
    ) -> bool:
        try:
            if thread_id:
                await self._delete_item(element_id, thread_id)
                return True

            query = (
                "SELECT TOP 1 c.id, c." + self.partition_key_field + " FROM c "
                "WHERE c.id = @id"
            )
            items = await self._query(
                query,
                parameters=[self._parameter("@id", element_id)],
                cross_partition=True,
                max_item_count=1,
            )
            if not items:
                return False

            await self._delete_item(
                items[0]["id"],
                items[0][self.partition_key_field],
            )
            return True
        except Exception:
            logger.exception("Failed to delete element")
            return False

    # ------------------------------------------------------------------
    # STEPS
    # ------------------------------------------------------------------

    async def get_steps(self, step_id: str) -> Optional[List[StepDict]]:
        query = "SELECT * FROM c WHERE c.id = @id"
        items = await self._query(
            query,
            parameters=[self._parameter("@id", step_id)],
            cross_partition=True,
        )
        return [self._strip_cosmos_meta(item) for item in items] or None

    @queue_until_user_message()
    async def create_step(self, step_dict: StepDict) -> None:
        item = dict(step_dict)
        item.setdefault("type", "step")
        item.setdefault("createdAt", self._timestamp())
        item.setdefault("ttl", TTL_30_DAYS)
        await self._upsert(item)

    @queue_until_user_message()
    async def update_step(self, step_dict: StepDict) -> None:
        item = dict(step_dict)
        if not item.get("id"):
            raise ValueError("update_step requires a step id.")

        item.setdefault("type", "step")
        item.setdefault("updatedAt", self._timestamp())
        await self._upsert(item)

    @queue_until_user_message()
    async def delete_step(
        self,
        step_id: str,
        thread_id: Optional[str] = None,
    ) -> bool:
        if not step_id:
            return False

        try:
            if thread_id:
                await self._delete_item(step_id, thread_id)
                return True

            items = await self.get_steps(step_id)
            if not items:
                return False

            for item in items:
                await self._delete_item(
                    item["id"],
                    item[self.partition_key_field],
                )
            return True
        except Exception:
            logger.exception("Failed to delete step")
            return False

    # ------------------------------------------------------------------
    # THREADS
    # ------------------------------------------------------------------

    async def get_thread_author(self, thread_id: str) -> Optional[str]:
        query = (
            "SELECT TOP 1 c.userId, c.userIdentifier FROM c "
            "WHERE c.type = @type AND c.id = @id"
        )
        items = await self._query(
            query,
            parameters=[
                self._parameter("@type", "thread"),
                self._parameter("@id", thread_id),
            ],
            partition_key=thread_id,
            max_item_count=1,
        )
        return items[0].get("userIdentifier") if items else None

    async def delete_thread(self, thread_id: str) -> None:
        """Soft-delete a thread while retaining its history."""
        thread = await self.get_thread(thread_id)
        if not thread:
            return

        thread["isActive"] = False
        thread["updatedAt"] = self._timestamp()
        await self._upsert(thread)

    async def hard_delete_thread(self, thread_id: str) -> bool:
        """Delete the thread and all thread-scoped descendants."""
        if not thread_id:
            return False

        try:
            query = (
                "SELECT c.id, c." + self.partition_key_field + " FROM c "
                "WHERE c." + self.partition_key_field + " = @threadId"
            )
            items = await self._query(
                query,
                parameters=[self._parameter("@threadId", thread_id)],
                partition_key=thread_id,
            )

            for item in items:
                await self._delete_item(
                    item["id"],
                    item[self.partition_key_field],
                )
            return True
        except Exception:
            logger.exception("Failed to hard-delete thread %s", thread_id)
            return False

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        if not thread_id:
            return None

        query = (
            "SELECT * FROM c "
            "WHERE (c.threadId = @threadId OR c.id = @threadId) "
            "AND (c.type != @threadType OR c.isActive = true)"
        )
        items = await self._query(
            query,
            parameters=[
                self._parameter("@threadId", thread_id),
                self._parameter("@threadType", "thread"),
            ],
            partition_key=thread_id,
        )

        if not items:
            return None

        thread_data: Optional[Dict[str, Any]] = None
        steps: List[Dict[str, Any]] = []
        elements: List[Dict[str, Any]] = []

        for raw_item in items:
            item = self._strip_cosmos_meta(raw_item)
            item_type = item.get("type")

            if item_type == "thread":
                thread_data = item
            elif item_type in self.message_step_types:
                feedback = await self.get_feedback(item.get("id"))
                if feedback:
                    item["feedback"] = feedback
                steps.append(item)
            elif item_type in self.element_types or item_type == "element":
                elements.append(item)

        if thread_data is None:
            return None

        steps.sort(key=lambda value: value.get("createdAt") or "")
        elements.sort(key=lambda value: value.get("createdAt") or "")

        thread_data["steps"] = steps
        thread_data["elements"] = elements
        return thread_data

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> Any:
        if not thread_id:
            raise ValueError("thread_id is required.")

        thread = await self._get_thread_item(thread_id)
        now = self._timestamp()

        if thread is None:
            thread = {
                "id": thread_id,
                "type": "thread",
                "createdAt": now,
                "updatedAt": now,
                "isActive": True,
            }

        if name is not None:
            thread["name"] = name
        else:
            thread.setdefault("name", now)

        thread["updatedAt"] = now
        thread["isActive"] = thread.get("isActive", True)
        thread["userId"] = user_id or thread.get("userId") or self.user_id
        thread["userIdentifier"] = (
            thread.get("userIdentifier") or self.user_identity
        )

        if metadata is not None:
            thread["metadata"] = metadata
            if metadata.get("is_guest") is True:
                thread.setdefault("ttl", TTL_30_DAYS)

        if tags is not None:
            thread["tags"] = tags

        return await self._upsert(thread)

    async def _get_thread_item(self, thread_id: str) -> Optional[Dict[str, Any]]:
        query = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.type = @type AND c.id = @id"
        )
        items = await self._query(
            query,
            parameters=[
                self._parameter("@type", "thread"),
                self._parameter("@id", thread_id),
            ],
            partition_key=thread_id,
            max_item_count=1,
        )
        return self._strip_cosmos_meta(items[0]) if items else None

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        """List active threads using Cosmos continuation-token pagination.

        ``Pagination.cursor`` is treated as the Cosmos continuation token.
        This avoids loading the complete thread history into application memory.
        """
        first = max(1, int(getattr(pagination, "first", 20) or 20))
        cursor = getattr(pagination, "cursor", None)

        where_clauses = [
            "c.type = @threadType",
            "c.isActive = true",
        ]
        parameters = [self._parameter("@threadType", "thread")]

        user_id = getattr(filters, "userId", None)
        if user_id:
            where_clauses.append("c.userId = @userId")
            parameters.append(self._parameter("@userId", user_id))

        search = getattr(filters, "search", None)
        if search:
            where_clauses.append("CONTAINS(c.name, @search, true)")
            parameters.append(self._parameter("@search", search))

        query = (
            "SELECT * FROM c WHERE "
            + " AND ".join(where_clauses)
            + " ORDER BY c.createdAt DESC"
        )

        continuation_token: Optional[str] = None

        def capture_headers(headers: Dict[str, Any]) -> None:
            nonlocal continuation_token
            continuation_token = (
                headers.get("x-ms-continuation")
                or headers.get("x-ms-continuation-token")
            )

        kwargs: Dict[str, Any] = {
            "query": query,
            "parameters": parameters,
            "enable_cross_partition_query": True,
            "max_item_count": first,
            "response_hook": capture_headers,
        }

        if cursor:
            kwargs["continuation_token"] = cursor

        iterator = await asyncio.to_thread(
            lambda: self.container.query_items(**kwargs)
        )
        items = await asyncio.to_thread(lambda: list(iterator))
        threads = [
            self._strip_cosmos_meta(item)
            for item in items
        ]

        return PaginatedResponse(
            data=threads,
            pageInfo=PageInfo(
                hasNextPage=bool(continuation_token),
                startCursor=cursor,
                endCursor=continuation_token,
            ),
        )

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        """Return favorite steps when the application marks them as favorites."""
        if not user_id:
            return []

        query = (
            "SELECT * FROM c "
            "WHERE c.type IN (@stepType, @userStepType, @assistantStepType) "
            "AND c.userId = @userId AND c.isFavorite = true "
            "ORDER BY c.createdAt DESC"
        )
        items = await self._query(
            query,
            parameters=[
                self._parameter("@stepType", "step"),
                self._parameter("@userStepType", "user_message"),
                self._parameter("@assistantStepType", "assistant_message"),
                self._parameter("@userId", user_id),
            ],
            cross_partition=True,
        )
        return [
            self._strip_cosmos_meta(item)
            for item in items
        ]

    # ------------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release the Cosmos client when Chainlit shuts down."""
        if self._closed:
            return

        self._closed = True
        close = getattr(self.client, "close", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result

    async def build_debug_url(self) -> Optional[str]:
        return ""
