import logging
import sqlite3
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class HITLQueueManager:
    """
    Manages the Human-in-the-Loop review queue backed by SQLite for robust local operation.
    Documents with low extraction confidence are routed here.
    """
    def __init__(self, db_path: str = "hitl_queue.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS hitl_queue (
                        id TEXT PRIMARY KEY,
                        file_path TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        resolved_at TEXT,
                        resolution_data TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize HITL database: {e}")

    def enqueue(self, file_path: Path, reason: str) -> str:
        """
        Adds a document to the manual review queue.
        """
        logger.info(f"Enqueuing {file_path.name} to HITL review. Reason: {reason}")
        item_id = str(uuid.uuid4())
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO hitl_queue (id, file_path, reason, status, created_at) VALUES (?, ?, ?, ?, ?)",
                    (item_id, str(file_path), reason, "PENDING", datetime.utcnow().isoformat())
                )
                conn.commit()
            return item_id
        except Exception as e:
            logger.error(f"Failed to enqueue document: {e}")
            return ""
        
    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """
        Retrieves items pending review.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM hitl_queue WHERE status = 'PENDING'")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch pending reviews: {e}")
            return []
        
    def resolve_review(self, item_id: str, corrected_data: Dict[str, Any]) -> bool:
        """
        Accepts human corrections, updates status, and potentially re-inserts into pipeline.
        """
        logger.info(f"Resolving review for item {item_id}")
        try:
            data_json = json.dumps(corrected_data)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE hitl_queue SET status = 'RESOLVED', resolved_at = ?, resolution_data = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), data_json, item_id)
                )
                if cursor.rowcount == 0:
                    logger.warning(f"No pending HITL item found with id {item_id}")
                    return False
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to resolve review {item_id}: {e}")
            return False
