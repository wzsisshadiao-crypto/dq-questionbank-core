"""Reference SQLite storage for canonical question sets.

This adapter implements the public ``StorageAdapter`` protocol with only the
Python standard library ``sqlite3`` module. It stores the canonical JSON
payload of one question set per row:

- ``save(question_set)`` writes the canonical payload deterministically.
  Saving an identifier that already exists **replaces the previous row in
  full** — last write wins, no history is kept, and no partial update can
  occur because each save is one transaction.
- ``load(question_set_id)`` returns the canonical ``QuestionSet`` and
  verifies that the stored identifier matches the request.

The adapter keeps the core database-neutral: it is a reference example of a
writable adapter, not the default backend, and it never opens or upgrades a
production database. Applications needing migrations, concurrency control,
users, or media should implement ``StorageAdapter`` in their own package.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .models import QuestionSet

_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS question_sets (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    question_count INTEGER NOT NULL
)
"""


class SqliteStorageAdapter:
    """Store canonical question sets in a single local SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()
        parent = self._path.parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path)
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def close(self) -> None:
        """Close the underlying connection."""
        self._connection.close()

    def __enter__(self) -> SqliteStorageAdapter:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def save(self, question_set: QuestionSet) -> None:
        """Atomically replace the stored row for ``question_set.id``.

        Repeated saves of the same payload produce the same stored bytes:
        the canonical JSON serialization is deterministic and one
        ``INSERT OR REPLACE`` runs inside a single transaction. Saving an
        existing identifier replaces the previous content entirely; this
        duplicate-id behavior is intentional and documented.
        """
        if not isinstance(question_set, QuestionSet):
            raise TypeError("SqliteStorageAdapter.save requires a QuestionSet.")
        identifier = self._validate_identifier(question_set.id)
        payload = json.dumps(
            question_set.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        )
        with self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO question_sets "
                "(id, payload, schema_version, question_count) "
                "VALUES (?, ?, ?, ?)",
                (
                    identifier,
                    payload,
                    question_set.schema_version,
                    len(question_set.questions),
                ),
            )

    def load(self, question_set_id: str) -> QuestionSet:
        """Load one canonical question set by its identifier.

        Raises ``KeyError`` when the identifier has never been saved. The
        stored payload must deserialize into the requested identifier;
        anything else fails closed.
        """
        identifier = self._validate_identifier(question_set_id)
        row = self._connection.execute(
            "SELECT payload FROM question_sets WHERE id = ?", (identifier,)
        ).fetchone()
        if row is None:
            raise KeyError(f"No stored question set with id {identifier!r}.")
        try:
            payload = json.loads(row[0])
        except json.JSONDecodeError as exc:
            raise ValueError("Stored question set is not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Stored question set must be a JSON object.")
        question_set = QuestionSet.from_dict(payload)
        if question_set.id != identifier:
            raise ValueError("Stored question-set identifier does not match its row.")
        return question_set

    def contains(self, question_set_id: str) -> bool:
        """Return whether an identifier has a stored row."""
        identifier = self._validate_identifier(question_set_id)
        row = self._connection.execute(
            "SELECT 1 FROM question_sets WHERE id = ?", (identifier,)
        ).fetchone()
        return row is not None

    def stored_ids(self) -> list[str]:
        """Return every stored identifier in deterministic sorted order."""
        rows = self._connection.execute(
            "SELECT id FROM question_sets ORDER BY id"
        ).fetchall()
        return [row[0] for row in rows]

    @staticmethod
    def _validate_identifier(question_set_id: str) -> str:
        if not isinstance(question_set_id, str) or not _SAFE_IDENTIFIER.fullmatch(
            question_set_id
        ):
            raise ValueError(
                "Question-set identifiers must use letters, digits, dots, "
                "hyphens, or underscores."
            )
        return question_set_id
