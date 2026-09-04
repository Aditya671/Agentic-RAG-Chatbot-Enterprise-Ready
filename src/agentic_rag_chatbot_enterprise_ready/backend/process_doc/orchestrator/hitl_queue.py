"""SQLite-backed human-in-the-loop review queue."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class HITLQueueManager:
    """Persist pending document-review work with explicit state transitions."""

    def __init__(self, db_path: str = "hitl_queue.db") -> None:
        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("db_path must be a non-empty string.")
        self.db_path = str(Path(db_path).expanduser())
        self._init_db()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        if path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10.0)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _init_db(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS hitl_queue (
                        id TEXT PRIMARY KEY,
                        file_path TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('PENDING', 'RESOLVED')),
                        created_at TEXT NOT NULL,
                        resolved_at TEXT,
                        resolution_data TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_hitl_queue_status_created "
                    "ON hitl_queue(status, created_at)"
                )
        except sqlite3.Error as exc:
            raise RuntimeError("Failed to initialize HITL database.") from exc

    def enqueue(self, file_path: Path, reason: str) -> str:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        if not reason or not str(reason).strip():
            raise ValueError("reason is required.")

        item_id = str(uuid.uuid4())
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO hitl_queue "
                    "(id, file_path, reason, status, created_at) VALUES (?, ?, ?, ?, ?)",
                    (item_id, str(file_path.resolve()), str(reason), "PENDING", self._now_iso()),
                )
            return item_id
        except sqlite3.Error as exc:
            logger.exception("Failed to enqueue document %s", file_path)
            raise RuntimeError("Failed to enqueue HITL review item.") from exc

    def get_pending_reviews(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM hitl_queue WHERE status = 'PENDING' "
                    "ORDER BY created_at ASC"
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logger.exception("Failed to fetch pending reviews")
            raise RuntimeError("Failed to fetch pending HITL reviews.") from exc

    def resolve_review(self, item_id: str, corrected_data: dict[str, Any]) -> bool:
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("item_id is required.")
        if not isinstance(corrected_data, dict):
            raise TypeError("corrected_data must be a dictionary.")

        try:
            data_json = json.dumps(corrected_data)
            with self._connect() as conn:
                cursor = conn.execute(
                    "UPDATE hitl_queue SET status = 'RESOLVED', resolved_at = ?, "
                    "resolution_data = ? WHERE id = ? AND status = 'PENDING'",
                    (self._now_iso(), data_json, item_id),
                )
                if cursor.rowcount != 1:
                    return False
            return True
        except (sqlite3.Error, TypeError, ValueError) as exc:
            logger.exception("Failed to resolve review %s", item_id)
            raise RuntimeError("Failed to resolve HITL review.") from exc
