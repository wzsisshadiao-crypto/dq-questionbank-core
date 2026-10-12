"""Rebuildable, optional FTS5 side index for local-workspace question stems.

The canonical JSON files remain authoritative. This cache never migrates or
modifies them, and an unavailable SQLite FTS5 module falls back to a scan.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dq_questionbank.models import Content

if TYPE_CHECKING:
    from .storage import WorkspaceStorage


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    set_id TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS stems USING fts5(
    set_id UNINDEXED,
    question_id UNINDEXED,
    stem
);
"""


def _stem_text(question: dict[str, Any]) -> str:
    return Content.from_dict(question.get("stem")).plain_text()


class StemSearchIndex:
    """Search one workspace with an FTS5 cache and a safe substring fallback."""

    def __init__(self, storage: WorkspaceStorage) -> None:
        self._storage = storage
        self.path = storage.root / ".dq-stem-search-v1.sqlite3"
        self._dirty: set[str] = set()
        self._lock = threading.RLock()

    def invalidate(self, set_id: str) -> None:
        """Mark a completed canonical JSON save for re-projection."""
        with self._lock:
            self._dirty.add(set_id)

    def search(self, set_id: str, query: str) -> dict[str, Any]:
        """Return ordered IDs for a literal token phrase, or a substring scan.

        The mode in the response is essential: FTS token/phrase matching and
        substring matching are deliberately not described as equivalent.
        """
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise ValueError("Search query must contain 1-256 characters.")
        query = query.strip()
        source = self._storage._path_for(set_id)
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(set_id)
        with self._lock:
            try:
                if self.path.is_symlink():
                    raise sqlite3.DatabaseError("Search cache cannot be a symbolic link.")
                return self._search_fts(set_id, query, source)
            except sqlite3.Error:
                payload = self._storage.load(set_id)
                needle = query.casefold()
                return {
                    "ids": [
                        question["id"]
                        for question in payload["questions"]
                        if needle in _stem_text(question).casefold()
                    ],
                    "mode": "substring-fallback",
                }

    def _search_fts(self, set_id: str, query: str, source: Path) -> dict[str, Any]:
        # Quoting makes operator-like user text literal instead of executable
        # FTS syntax. Punctuation-only searches use the substring fallback.
        if not any(char.isalnum() for char in query):
            raise sqlite3.OperationalError("No FTS token in query.")
        phrase = '"' + query.replace('"', '""') + '"'
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript(_SCHEMA)
            self._prune_missing_sources(connection)
            stat = source.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            indexed = connection.execute(
                "SELECT size, mtime_ns FROM sources WHERE set_id = ?", (set_id,)
            ).fetchone()
            if set_id in self._dirty or indexed != signature:
                payload = self._storage.load(set_id)
                # Do not certify a projection of bytes that changed during load.
                latest = source.stat()
                if (latest.st_size, latest.st_mtime_ns) != signature:
                    raise sqlite3.OperationalError("Source changed while indexing.")
                with connection:
                    connection.execute("DELETE FROM stems WHERE set_id = ?", (set_id,))
                    connection.executemany(
                        "INSERT INTO stems (set_id, question_id, stem) VALUES (?, ?, ?)",
                        (
                            (set_id, question["id"], _stem_text(question))
                            for question in payload["questions"]
                        ),
                    )
                    connection.execute(
                        "INSERT OR REPLACE INTO sources (set_id, size, mtime_ns) "
                        "VALUES (?, ?, ?)",
                        (set_id, *signature),
                    )
                self._dirty.discard(set_id)
            rows = connection.execute(
                "SELECT question_id FROM stems WHERE stems MATCH ? AND set_id = ? "
                "ORDER BY rowid",
                (phrase, set_id),
            ).fetchall()
        return {"ids": [row[0] for row in rows], "mode": "fts5-phrase"}

    def _prune_missing_sources(self, connection: sqlite3.Connection) -> None:
        """Discard cache rows for canonical files removed outside the app."""
        missing = []
        for (set_id,) in connection.execute("SELECT set_id FROM sources"):
            try:
                source = self._storage._path_for(set_id)
                if source.is_file() and not source.is_symlink():
                    continue
            except ValueError:
                pass
            missing.append(set_id)
        if missing:
            with connection:
                connection.executemany(
                    "DELETE FROM stems WHERE set_id = ?", ((item,) for item in missing)
                )
                connection.executemany(
                    "DELETE FROM sources WHERE set_id = ?", ((item,) for item in missing)
                )
