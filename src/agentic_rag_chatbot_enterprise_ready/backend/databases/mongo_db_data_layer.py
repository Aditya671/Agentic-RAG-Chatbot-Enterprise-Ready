"""MongoDB-backed Chainlit data layer.

Uses PyMongo's native asyncio API. Motor was deprecated by MongoDB in 2026;
new async applications should use ``pymongo.AsyncMongoClient`` instead.

The implementation keeps the existing MongoDB document model and public class
name while bringing the data-layer contract in line with current Chainlit
requirements.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from chainlit import PersistedUser, User
from chainlit.data.base import BaseDataLayer
from chainlit.data.utils import queue_until_user_message
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


class MongoDBDataLayer(BaseDataLayer):
    """Chainlit-compatible MongoDB persistence layer."""

    USER_TYPE = "user"
    THREAD_TYPE = "thread"
    FEEDBACK_TYPE = "feedback"
    SESSION_TYPE = "user_session"

    MESSAGE_STEP_TYPES = frozenset(
        {"user_message", "assistant_message", "system_message"}
    )
    ELEMENT_TYPES = frozenset(
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
        connection_string: str,
        database_name: str,
        collection_name: str = "chainlit_data",
        *,
        max_pool_size: int = 100,
        min_pool_size: int = 0,
        server_selection_timeout_ms: int = 5000,
    ) -> None:
        if not connection_string or not connection_string.strip():
            raise ValueError("connection_string must be a non-empty string.")
        if not database_name or not database_name.strip():
            raise ValueError("database_name must be a non-empty string.")
        if not collection_name or not collection_name.strip():
            raise ValueError("collection_name must be a non-empty string.")

        self.client = AsyncMongoClient(
            connection_string,
            maxPoolSize=max_pool_size,
            minPoolSize=min_pool_size,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
        )
        self.db = self.client[database_name]
        self.collection = self.db[collection_name]

    @staticmethod
    def _timestamp() -> str:
        """Return a stable UTC timestamp compatible with Chainlit string fields."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _format_document(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Return a detached Chainlit-safe document without mutating Mongo data."""
        if not doc:
            return None

        result = dict(doc)
        mongo_id = result.pop("_id", None)
        if mongo_id is not None:
            result["id"] = str(mongo_id)
        return result

    @staticmethod
    def _encode_cursor(created_at: str, document_id: str) -> str:
        payload = json.dumps(
            {"createdAt": created_at, "id": document_id},
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: Optional[str]) -> Optional[Dict[str, str]]:
        if not cursor:
            return None

        try:
            padding = "=" * (-len(cursor) % 4)
            payload = base64.urlsafe_b64decode(
                cursor + padding
            ).decode("utf-8")
            value = json.loads(payload)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid pagination cursor.") from exc

        if not isinstance(value, dict) or not value.get("createdAt") or not value.get(
            "id"
        ):
            raise ValueError("Invalid pagination cursor.")

        return {
            "createdAt": str(value["createdAt"]),
            "id": str(value["id"]),
        }

    @staticmethod
    def _pagination_cursor(pagination: Pagination) -> Optional[str]:
        """Support Chainlit cursor naming without depending on one model version."""
        return getattr(pagination, "cursor", None) or getattr(
            pagination, "after", None
        )

    @staticmethod
    def _element_to_dict(element_dict: ElementDict) -> Dict[str, Any]:
        if hasattr(element_dict, "to_dict"):
            return dict(element_dict.to_dict())
        return dict(element_dict)

    async def initialize_indexes(self) -> None:
        """Create indexes required by user, thread, feedback, and retrieval paths."""
        await self.collection.create_indexes(
            [
                {
                    "keys": [
                        ("type", ASCENDING),
                        ("identifier", ASCENDING),
                    ],
                    "unique": True,
                    "name": "user_identifier_unique",
                    "partialFilterExpression": {"type": self.USER_TYPE},
                },
                {
                    "keys": [
                        ("type", ASCENDING),
                        ("userId", ASCENDING),
                        ("createdAt", DESCENDING),
                        ("_id", DESCENDING),
                    ],
                    "name": "active_thread_listing",
                },
                {
                    "keys": [
                        ("threadId", ASCENDING),
                        ("createdAt", ASCENDING),
                    ],
                    "name": "thread_children",
                },
                {
                    "keys": [
                        ("type", ASCENDING),
                        ("forId", ASCENDING),
                    ],
                    "unique": True,
                    "name": "feedback_step_unique",
                    "partialFilterExpression": {"type": self.FEEDBACK_TYPE},
                },
                {
                    "keys": [
                        ("type", ASCENDING),
                        ("userId", ASCENDING),
                        ("createdAt", DESCENDING),
                    ],
                    "name": "favorite_steps",
                },
            ]
        )

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        if not identifier:
            return None

        row = await self.collection.find_one(
            {"type": self.USER_TYPE, "identifier": identifier}
        )
        if not row:
            return None

        return PersistedUser(
            id=str(row["_id"]),
            display_name=str(row.get("displayName") or identifier),
            identifier=str(row["identifier"]),
            createdAt=row.get("createdAt"),
            metadata=row.get("metadata", {}),
        )

    async def create_user(self, user: User) -> PersistedUser:
        identifier = str(user.identifier)
        if not identifier or identifier == "None":
            raise ValueError("Cannot create a user without a valid identifier.")

        metadata = dict(user.metadata or {})
        display_name = (
            metadata.get("claims", {}).get("displayName")
            if isinstance(metadata.get("claims"), dict)
            else None
        )

        now = self._timestamp()
        user_id = str(__import__("uuid").uuid4())

        document = {
            "_id": user_id,
            "identifier": identifier,
            "type": self.USER_TYPE,
            "displayName": display_name,
            "metadata": metadata,
            "createdAt": now,
            "updatedAt": now,
        }

        try:
            await self.collection.insert_one(document)
        except DuplicateKeyError:
            existing = await self.collection.find_one(
                {"type": self.USER_TYPE, "identifier": identifier}
            )
            if not existing:
                raise

            existing_metadata = dict(existing.get("metadata") or {})
            if "groups" in metadata:
                existing_metadata["groups"] = metadata["groups"]

            await self.collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "metadata": existing_metadata,
                        "updatedAt": now,
                    }
                },
            )

            return PersistedUser(
                id=str(existing["_id"]),
                display_name=str(existing.get("displayName") or identifier),
                identifier=identifier,
                createdAt=existing.get("createdAt"),
                metadata=existing_metadata,
            )

        return PersistedUser(
            id=user_id,
            display_name=str(display_name or identifier),
            identifier=identifier,
            createdAt=now,
            metadata=metadata,
        )

    async def get_feedback(self, step_id: str) -> Optional[Dict[str, Any]]:
        feedback = await self.collection.find_one(
            {"type": self.FEEDBACK_TYPE, "forId": step_id}
        )
        return self._format_document(feedback)

    async def upsert_feedback(self, feedback: Feedback) -> str:
        feedback_id = str(getattr(feedback, "id", None) or __import__("uuid").uuid4())
        now = self._timestamp()

        thread_id = str(feedback.threadId)
        thread = await self.collection.find_one(
            {"_id": thread_id, "type": self.THREAD_TYPE},
            projection={"userId": 1},
        )
        user_id = getattr(feedback, "userId", None) or (
            str(thread.get("userId")) if thread else None
        )

        feedback_dict = {
            "_id": feedback_id,
            "type": self.FEEDBACK_TYPE,
            "forId": feedback.forId,
            "threadId": feedback.threadId,
            "value": feedback.value,
            "comment": feedback.comment,
            "userId": user_id,
            "updatedAt": now,
        }

        await self.collection.update_one(
            {"type": self.FEEDBACK_TYPE, "forId": feedback.forId},
            {
                "$set": feedback_dict,
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )
        return feedback_id

    async def delete_feedback(self, feedback_id: str) -> bool:
        result = await self.collection.delete_one(
            {"type": self.FEEDBACK_TYPE, "_id": feedback_id}
        )
        return result.deleted_count > 0

    @queue_until_user_message()
    async def create_step(self, step_dict: StepDict) -> None:
        step = dict(step_dict)
        step_id = step.pop("id", None)
        if not step_id:
            raise ValueError("Step id is required.")

        step["_id"] = str(step_id)
        step.setdefault("type", "step")
        step.setdefault("createdAt", self._timestamp())
        await self.collection.replace_one(
            {"_id": step["_id"]},
            step,
            upsert=True,
        )

    @queue_until_user_message()
    async def update_step(self, step_dict: StepDict) -> None:
        step = dict(step_dict)
        step_id = step.pop("id", None)
        if not step_id:
            raise ValueError("Step id is required.")

        step["updatedAt"] = self._timestamp()
        await self.collection.update_one(
            {"_id": str(step_id)},
            {"$set": step},
            upsert=False,
        )

    async def delete_step(self, step_id: str) -> bool:
        result = await self.collection.delete_one(
            {"_id": str(step_id), "type": {"$in": list(self.MESSAGE_STEP_TYPES) + ["step"]}}
        )
        return result.deleted_count > 0

    @queue_until_user_message()
    async def create_element(self, element_dict: ElementDict) -> None:
        element = self._element_to_dict(element_dict)
        element_id = element.pop("id", None)
        if not element_id:
            raise ValueError("Element id is required.")

        element["_id"] = str(element_id)
        element.setdefault("type", "element")
        element.setdefault("createdAt", self._timestamp())

        await self.collection.replace_one(
            {"_id": element["_id"]},
            element,
            upsert=True,
        )

    async def get_element(
        self,
        thread_id: str,
        element_id: str,
    ) -> Optional[ElementDict]:
        element = await self.collection.find_one(
            {
                "_id": str(element_id),
                "threadId": thread_id,
            }
        )
        return self._format_document(element)  # type: ignore[return-value]

    async def delete_element(self, element_id: str) -> bool:
        result = await self.collection.delete_one(
            {
                "_id": str(element_id),
                "type": {"$in": list(self.ELEMENT_TYPES) + ["element"]},
            }
        )
        return result.deleted_count > 0

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        thread = await self.collection.find_one(
            {"_id": str(thread_id), "type": self.THREAD_TYPE}
        )
        if not thread or not thread.get("isActive", True):
            return None

        children = await self.collection.find(
            {"threadId": str(thread_id)}
        ).sort("createdAt", ASCENDING).to_list(None)

        steps: List[Dict[str, Any]] = []
        elements: List[Dict[str, Any]] = []

        for raw_item in children:
            item = self._format_document(raw_item)
            if not item:
                continue

            item_type = item.get("type")
            if item_type in self.MESSAGE_STEP_TYPES or item_type == "step":
                steps.append(item)
            elif item_type in self.ELEMENT_TYPES or item_type == "element":
                elements.append(item)

        # Avoid an N+1 feedback query: load all feedback for the thread at once.
        if steps:
            step_ids = [step["id"] for step in steps if step.get("id")]
            feedback_items = await self.collection.find(
                {
                    "type": self.FEEDBACK_TYPE,
                    "forId": {"$in": step_ids},
                }
            ).to_list(None)

            feedback_by_step = {
                str(item["forId"]): self._format_document(item)
                for item in feedback_items
            }

            for step in steps:
                step["feedback"] = feedback_by_step.get(str(step.get("id")))

        result = self._format_document(thread)
        result["steps"] = steps
        result["elements"] = elements
        return result  # type: ignore[return-value]

    async def get_thread_author(self, thread_id: str) -> Optional[str]:
        thread = await self.collection.find_one(
            {"_id": str(thread_id), "type": self.THREAD_TYPE},
            projection={"userIdentifier": 1},
        )
        if not thread:
            return None
        return thread.get("userIdentifier")

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        now = self._timestamp()
        update_fields: Dict[str, Any] = {
            "updatedAt": now,
            "isActive": True,
            "type": self.THREAD_TYPE,
        }

        if user_id is not None:
            update_fields["userId"] = user_id

        if name is not None:
            update_fields["name"] = name

        if metadata is not None:
            update_fields["metadata"] = metadata

        if tags is not None:
            update_fields["tags"] = tags

        # userIdentifier is derived only when the supplied user_id maps to a
        # persisted user. We do not rely on mutable per-process user state.
        if user_id is not None:
            user = await self.collection.find_one(
                {"_id": str(user_id), "type": self.USER_TYPE},
                projection={"identifier": 1},
            )
            if user:
                update_fields["userIdentifier"] = user["identifier"]

        await self.collection.update_one(
            {"_id": str(thread_id), "type": self.THREAD_TYPE},
            {
                "$set": update_fields,
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        first = max(int(pagination.first or 0), 0)
        if first == 0:
            return PaginatedResponse(
                data=[],
                pageInfo=PageInfo(
                    hasNextPage=False,
                    startCursor=None,
                    endCursor=None,
                ),
            )

        query: Dict[str, Any] = {
            "type": self.THREAD_TYPE,
            "isActive": True,
        }

        if getattr(filters, "userId", None):
            query["userId"] = filters.userId

        if getattr(filters, "search", None):
            # Escape user input so it cannot accidentally become a Mongo regex.
            import re

            query["name"] = {
                "$regex": re.escape(filters.search),
                "$options": "i",
            }

        cursor_value = self._decode_cursor(self._pagination_cursor(pagination))
        if cursor_value:
            # createdAt is the primary descending key; _id is the tie-breaker.
            query["$or"] = [
                {"createdAt": {"$lt": cursor_value["createdAt"]}},
                {
                    "createdAt": cursor_value["createdAt"],
                    "_id": {"$lt": cursor_value["id"]},
                },
            ]

        rows = await self.collection.find(query).sort(
            [("createdAt", DESCENDING), ("_id", DESCENDING)]
        ).limit(first + 1).to_list(first + 1)

        has_next_page = len(rows) > first
        visible = rows[:first]
        data = [self._format_document(row) for row in visible]

        start_cursor = None
        end_cursor = None
        if data:
            start_cursor = self._encode_cursor(
                str(data[0].get("createdAt", "")),
                str(data[0]["id"]),
            )
            end_cursor = self._encode_cursor(
                str(data[-1].get("createdAt", "")),
                str(data[-1]["id"]),
            )

        return PaginatedResponse(
            data=data,
            pageInfo=PageInfo(
                hasNextPage=has_next_page,
                startCursor=start_cursor,
                endCursor=end_cursor,
            ),
        )

    async def delete_thread(self, thread_id: str) -> None:
        await self.collection.update_one(
            {"_id": str(thread_id), "type": self.THREAD_TYPE},
            {
                "$set": {
                    "isActive": False,
                    "updatedAt": self._timestamp(),
                }
            },
        )

    async def delete_user_session(self, id: str) -> bool:
        result = await self.collection.delete_one(
            {"_id": str(id), "type": self.SESSION_TYPE}
        )
        return result.deleted_count > 0

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        rows = await self.collection.find(
            {
                "userId": str(user_id),
                "type": {"$in": list(self.MESSAGE_STEP_TYPES) + ["step"]},
                "metadata.favorited": True,
            }
        ).sort("createdAt", DESCENDING).to_list(None)

        return [
            self._format_document(row)  # type: ignore[misc]
            for row in rows
        ]

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        """Close the native PyMongo async client during Chainlit shutdown."""
        await self.client.close()
