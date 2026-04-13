"""
Offline sync queue using SQLite.
When the server is unreachable, events are buffered locally.
On reconnection, queued events are flushed in order.
"""

import sqlite3
import json
import logging
import threading
from datetime import datetime
from typing import List, Optional

log = logging.getLogger("sync_queue")

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS event_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    last_attempt TEXT
);
"""

CREATE_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS agent_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class OfflineSyncQueue:
    """
    SQLite-backed queue for activity events when server is offline.
    Thread-safe via lock.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(CREATE_TABLE)
            conn.execute(CREATE_STATE_TABLE)
            conn.commit()

    def enqueue_batch(self, payload: dict):
        """Store a batch payload for later retry."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO event_queue (payload, created_at) VALUES (?, ?)",
                    (json.dumps(payload), datetime.utcnow().isoformat()),
                )
                conn.commit()
        log.debug("batch_queued_offline")

    def dequeue_batch(self, limit: int = 5) -> List[tuple[int, dict]]:
        """Get up to `limit` oldest queued batches for retry."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT id, payload FROM event_queue ORDER BY id ASC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [(row[0], json.loads(row[1])) for row in rows]

    def mark_sent(self, queue_ids: List[int]):
        """Remove successfully sent batches from queue."""
        if not queue_ids:
            return
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"DELETE FROM event_queue WHERE id IN ({','.join('?' * len(queue_ids))})",
                    queue_ids,
                )
                conn.commit()
        log.debug(f"offline_queue_cleared: {len(queue_ids)} batches")

    def mark_failed(self, queue_id: int):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE event_queue SET attempts = attempts + 1, last_attempt = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), queue_id),
                )
                conn.commit()

    def pending_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM event_queue").fetchone()[0]

    def save_state(self, key: str, value: str):
        """Persist agent state (e.g. device_token, session_id)."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO agent_state (key, value) VALUES (?, ?)",
                    (key, value),
                )
                conn.commit()

    def load_state(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM agent_state WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None
