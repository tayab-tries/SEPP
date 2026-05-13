"""
client/core/local_cache.py
Module 8 — Local Cache

Manages all local persistence during an exam session using SQLite.
Falls back gracefully between SQLCipher (encrypted) and plain SQLite (dev).

Optimizations implemented:
  - Answer writes only on actual content change (no redundant I/O)
  - Thread-safe via explicit lock on all write operations
  - In-memory answer hash tracking to detect changes without DB reads
  - Stale session data purged on init
"""

import json
import hashlib
import logging
import threading
from datetime import datetime
from typing import Optional, List
from pathlib import Path

try:
    from sqlcipher3 import dbapi2 as sqlite3
    ENCRYPTED = True
except ImportError:
    import sqlite3  # type: ignore
    ENCRYPTED = False
    logging.warning(
        "sqlcipher3 not found — using unencrypted SQLite (dev mode). "
        "Install sqlcipher3 for production."
    )

from client.config import LOCAL_DB_PATH, LOCAL_DB_KEY

logger = logging.getLogger(__name__)


class LocalCache:
    """
    Manages all local persistence during an exam session.

    Thread safety:
        All write operations are protected by self._lock.
        Reads are safe without locking (WAL mode allows concurrent reads).

    Answer change detection:
        self._answer_hashes tracks a hash of the last saved answer per question.
        save_answer() skips the DB write if content hasn't changed.
        This eliminates constant 3-second SQLite writes during idle periods.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # In-memory answer hash tracking
        # key: question_id, value: SHA256 hash of last saved content
        self._answer_hashes: dict[str, str] = {}

        self.conn = sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)

        if ENCRYPTED:
            self.conn.execute(f"PRAGMA key='{LOCAL_DB_KEY}'")
            logger.info("Local cache opened with SQLCipher encryption")
        else:
            logger.warning("Local cache running WITHOUT encryption (dev mode)")

        # WAL mode: allows concurrent reads while writing
        self.conn.execute("PRAGMA journal_mode=WAL")

        # Optimize for frequent small writes
        self.conn.execute("PRAGMA synchronous=NORMAL")

        self._create_tables()

    def _create_tables(self):
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS answers (
                    question_id     TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL,
                    selected_option TEXT,
                    answer_text     TEXT,
                    updated_at      TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id          TEXT PRIMARY KEY,
                    session_id  TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    severity    TEXT NOT NULL,
                    timestamp   TEXT NOT NULL,
                    metadata    TEXT,
                    snapshot_path TEXT,
                    synced      INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS session_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            # Backfill column for existing caches created before snapshot_path support.
            cols = [
                row[1] for row in self.conn.execute("PRAGMA table_info(events)").fetchall()
            ]
            if "snapshot_path" not in cols:
                self.conn.execute("ALTER TABLE events ADD COLUMN snapshot_path TEXT")
            self.conn.commit()

    # ── Session Metadata ───────────────────────────────────────────────────

    def set_meta(self, key: str, value: str):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO session_meta (key, value) VALUES (?, ?)",
                (key, value),
            )
            self.conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM session_meta WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def record_lockdown_start(self):
        """Record exact UTC time when network lockdown began."""
        self.set_meta("lockdown_start", datetime.utcnow().isoformat())

    def get_lockdown_start(self) -> Optional[datetime]:
        val = self.get_meta("lockdown_start")
        return datetime.fromisoformat(val) if val else None

    def clear_lockdown(self):
        with self._lock:
            self.conn.execute(
                "DELETE FROM session_meta WHERE key = 'lockdown_start'"
            )
            self.conn.commit()

    def purge_session(self, session_id: str):
        """
        Remove all data for a specific session.
        Called at exam start to clear any stale data from a previous
        crashed session before writing fresh data.
        """
        with self._lock:
            self.conn.execute(
                "DELETE FROM answers WHERE session_id = ?", (session_id,)
            )
            self.conn.execute(
                "DELETE FROM events WHERE session_id = ?", (session_id,)
            )
            self.conn.execute("DELETE FROM session_meta")
            self.conn.commit()

        # Clear in-memory hashes for this session
        self._answer_hashes.clear()
        logger.info(f"Purged stale local cache for session {session_id}")

    # ── Answer Management ──────────────────────────────────────────────────

    @staticmethod
    def _hash_answer(
    selected_option: Optional[str],
    answer_text: Optional[str],
    ) -> str:
        safe_option = selected_option if selected_option is not None else ""
        safe_text = answer_text if answer_text is not None else ""
        content = f"{safe_option}|{safe_text}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def save_answer(
        self,
        session_id: str,
        question_id: str,
        selected_option: Optional[str] = None,
        answer_text: Optional[str] = None,
    ) -> bool:
        """
        Upsert an answer to local cache.

        Optimization: skips DB write if content hasn't changed since last save.
        Returns True if actually written, False if skipped (no change).

        Called every 3 seconds by the auto-save timer in exam_window.py.
        On a typical essay question most calls will be skipped — only writes
        when the student has actually typed something new.
        """
        new_hash = self._hash_answer(selected_option, answer_text)
        last_hash = self._answer_hashes.get(question_id)

        if new_hash == last_hash:
            return False  # No change — skip write

        with self._lock:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO answers
                    (question_id, session_id, selected_option, answer_text, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    question_id,
                    session_id,
                    selected_option,
                    answer_text,
                    datetime.utcnow().isoformat(),
                ),
            )
            self.conn.commit()

        # Update in-memory hash only after successful write
        self._answer_hashes[question_id] = new_hash
        return True

    def get_all_answers(self, session_id: str) -> List[dict]:
        """Return all answers for a session — used for server sync."""
        rows = self.conn.execute(
            """
            SELECT question_id, selected_option, answer_text
            FROM answers
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchall()
        return [
            {
                "question_id": r[0],
                "selected_option": r[1],
                "answer_text": r[2],
            }
            for r in rows
        ]

    def get_answer(self, question_id: str) -> Optional[dict]:
        """Return a single answer by question_id — used to restore answers on reconnect."""
        row = self.conn.execute(
            """
            SELECT question_id, selected_option, answer_text
            FROM answers
            WHERE question_id = ?
            """,
            (question_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "question_id": row[0],
            "selected_option": row[1],
            "answer_text": row[2],
        }

    def has_unsaved_answers(self, session_id: str) -> bool:
        """Returns True if there are any answers in local cache for this session."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM answers WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row[0] > 0 if row else False

    # ── Event Queue ────────────────────────────────────────────────────────

    def queue_event(
        self,
        session_id: str,
        event_id: str,
        event_type: str,
        severity: str,
        timestamp: datetime,
        metadata: Optional[dict] = None,
        snapshot_path: Optional[str] = None,
    ):
        """
        Store a proctoring event locally.
        Will be flushed to server in batches by EventLogger.
        Uses INSERT OR IGNORE — duplicate event_ids are silently skipped.
        """
        with self._lock:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO events
                    (id, session_id, event_type, severity, timestamp, metadata, snapshot_path, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    event_id,
                    session_id,
                    event_type,
                    severity,
                    timestamp.isoformat(),
                    json.dumps(metadata) if metadata else None,
                    snapshot_path,
                ),
            )
            self.conn.commit()

    def get_unsynced_events(self, session_id: str) -> List[dict]:
        """Return all unsynced events ordered by timestamp ascending."""
        rows = self.conn.execute(
            """
            SELECT id, event_type, severity, timestamp, metadata, snapshot_path
            FROM events
            WHERE session_id = ? AND synced = 0
            ORDER BY timestamp ASC
            """,
            (session_id,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "event_type": r[1],
                "severity": r[2],
                "timestamp": r[3],
                "metadata": json.loads(r[4]) if r[4] else None,
                "snapshot_path": r[5],
            }
            for r in rows
        ]

    def get_unsynced_event_count(self, session_id: str) -> int:
        """Quick count of pending events — used to decide flush urgency."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ? AND synced = 0",
            (session_id,),
        ).fetchone()
        return row[0] if row else 0

    def mark_events_synced(self, event_ids: List[str]):
        """Mark a list of events as synced after successful server delivery."""
        if not event_ids:
            return
        placeholders = ",".join("?" * len(event_ids))
        with self._lock:
            self.conn.execute(
                f"UPDATE events SET synced = 1 WHERE id IN ({placeholders})",
                event_ids,
            )
            self.conn.commit()

    # ── Cleanup ────────────────────────────────────────────────────────────

    def close(self):
        """Close the database connection cleanly."""
        try:
            self.conn.close()
            logger.info("Local cache closed")
        except Exception as e:
            logger.error(f"Error closing local cache: {e}")