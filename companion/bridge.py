"""SQLite mailbox between Civ V Lua and the translation companion.

Protocol: Lua opens Modding.OpenUserData("InGameTranslateMod", 1), writes a
unique per-load token to igt_state['session'], and inserts requests. `created`
is Unix seconds (CAST(strftime('%s','now') AS REAL) works in Civ's SQLite).
Lua polls rows for its session with status done/error and reads result/error.
Only Lua sends chat; the companion never sends messages to another player.

The database uses ordinary rollback journaling for Civ V's older SQLite.
No transaction is held while translating. Result writes retry without repeating
the HTTP request while this worker remains alive. A process crash after HTTP
completion can cause a retry after the working lease expires.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS igt_state (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT,
    kind TEXT,
    source TEXT,
    target TEXT,
    text TEXT,
    status TEXT DEFAULT 'pending',
    result TEXT,
    detected TEXT,
    error TEXT,
    created REAL,
    started REAL
);
CREATE INDEX IF NOT EXISTS igt_requests_status ON requests(status, id);
"""


class Translator(Protocol):
    def translate(self, text: str, source: str, target: str) -> tuple[str, str]: ...


def _schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(requests)")}
    if "started" not in columns:
        connection.execute("ALTER TABLE requests ADD COLUMN started REAL")


def initialize_database(path: str | Path) -> None:
    """Create a protocol database for diagnostics/tests; game normally creates it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(path), isolation_level=None)) as connection:
        _schema(connection)


@dataclass
class _Completion:
    request_id: int
    session: str
    started: float
    status: str
    result: str = ""
    detected: str = ""
    error: str = ""


class Bridge:
    """Call process_one repeatedly from a background thread or console loop.

    The object is deliberately single-threaded. Separate workers safely claim
    separate requests, but only one worker is recommended to preserve ordering.
    False means no request was completed (idle, no database, or temporary busy).
    """

    def __init__(
        self,
        db_path: str | Path,
        translator: Translator,
        *,
        max_age_seconds: float = 120,
        working_timeout_seconds: float = 60,
        max_completed_rows: int = 1000,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.db_path = Path(db_path)
        self.translator = translator
        self.max_age_seconds = max_age_seconds
        self.working_timeout_seconds = working_timeout_seconds
        self.max_completed_rows = max_completed_rows
        self.clock = clock
        self._initialized = False
        self._completion: _Completion | None = None

    def _connect(self) -> sqlite3.Connection:
        # mode=rw prevents an accidental new database at a mistyped game path.
        connection = sqlite3.connect(
            self.db_path.resolve().as_uri() + "?mode=rw",
            uri=True,
            timeout=0.15,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _busy(error: sqlite3.OperationalError) -> bool:
        return "locked" in str(error).lower() or "busy" in str(error).lower()

    def _claim(self) -> sqlite3.Row | None:
        with closing(self._connect()) as connection:
            if not self._initialized:
                _schema(connection)
                self._initialized = True
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT value FROM igt_state WHERE key='session'"
            ).fetchone()
            if not current or not current[0]:
                connection.commit()
                return None
            session = current[0]
            now = self.clock()
            connection.execute(
                "UPDATE requests SET status='error', error='Game session ended.' "
                "WHERE status IN ('pending','working') AND (session IS NULL OR session<>?)",
                (session,),
            )
            connection.execute(
                "UPDATE requests SET status='error', error='Translation request expired.' "
                "WHERE status IN ('pending','working') AND "
                "(created IS NULL OR created<? OR created>?)",
                (now - self.max_age_seconds, now + 60),
            )
            connection.execute(
                "UPDATE requests SET status='pending', started=NULL "
                "WHERE status='working' AND session=? AND "
                "(started IS NULL OR started<?)",
                (session, now - self.working_timeout_seconds),
            )
            # Pending/current work is never removed by housekeeping.
            connection.execute(
                "DELETE FROM requests WHERE status IN ('done','error') AND id NOT IN "
                "(SELECT id FROM requests WHERE status IN ('done','error') "
                "ORDER BY id DESC LIMIT ?)",
                (self.max_completed_rows,),
            )
            row = connection.execute(
                "SELECT * FROM requests WHERE session=? AND status='pending' "
                "ORDER BY id LIMIT 1",
                (session,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                "UPDATE requests SET status='working', started=?, error=NULL WHERE id=?",
                (now, row["id"]),
            )
            row = connection.execute("SELECT * FROM requests WHERE id=?", (row["id"],)).fetchone()
            connection.commit()
            return row

    def _flush_completion(self) -> bool:
        item = self._completion
        if item is None:
            return False
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT value FROM igt_state WHERE key='session'"
            ).fetchone()
            status, result, detected, error = item.status, item.result, item.detected, item.error
            if not current or current[0] != item.session:
                status, result, detected, error = "error", "", "", "Game session ended."
            connection.execute(
                "UPDATE requests SET status=?, result=?, detected=?, error=? "
                "WHERE id=? AND session=? AND status='working' AND started=?",
                (status, result, detected, error, item.request_id, item.session, item.started),
            )
            connection.commit()
        self._completion = None
        return True

    def process_one(self) -> bool:
        if not self.db_path.is_file():
            return False
        try:
            if self._completion is not None:
                return self._flush_completion()
            row = self._claim()
            if row is None:
                return False
            item = _Completion(row["id"], row["session"], row["started"], "done")
            try:
                if row["kind"] not in ("incoming", "outgoing", "test"):
                    raise ValueError("Unknown translation request kind.")
                if not isinstance(row["text"], str) or not row["text"].strip():
                    raise ValueError("Message is empty.")
                if not isinstance(row["target"], str) or not row["target"].strip():
                    raise ValueError("Target language is missing.")
                result, detected = self.translator.translate(
                    row["text"], row["source"] or "auto", row["target"]
                )
                if not isinstance(result, str) or not result.strip():
                    raise ValueError("Translation provider returned empty text.")
                item.result, item.detected = result, str(detected or "")
            except Exception as error:
                item.status = "error"
                item.error = str(error)[:300] or type(error).__name__
            self._completion = item
            return self._flush_completion()
        except sqlite3.OperationalError as error:
            if self._busy(error):
                # Caller polls again; a translated result stays in memory.
                return False
            raise
