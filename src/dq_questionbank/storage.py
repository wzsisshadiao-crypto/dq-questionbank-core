"""Reference local filesystem storage for canonical question sets.

The adapter is intentionally small: it stores one canonical JSON document per
question-set identifier and does not manage users, databases, media, or locks.
Applications with those requirements should implement ``StorageAdapter`` in a
separate integration package.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .models import QuestionSet


_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class FilesystemStorageAdapter:
    """Store canonical question sets under a deterministic local directory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).expanduser().resolve()
        self._question_sets = self._root / "question_sets"

    def save(self, question_set: QuestionSet) -> None:
        """Atomically replace the JSON document for ``question_set.id``."""
        if not isinstance(question_set, QuestionSet):
            raise TypeError("FilesystemStorageAdapter.save requires a QuestionSet.")
        target = self._path_for(question_set.id)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError("Refusing to replace a symbolic-link storage target.")

        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.stem}.",
            suffix=".tmp",
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(question_set.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def load(self, question_set_id: str) -> QuestionSet:
        """Load one canonical question set without allowing path traversal."""
        target = self._path_for(question_set_id)
        if target.is_symlink():
            raise ValueError("Refusing to load a symbolic-link storage target.")
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Stored question set is not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Stored question set must be a JSON object.")
        question_set = QuestionSet.from_dict(payload)
        if question_set.id != question_set_id:
            raise ValueError("Stored question-set identifier does not match its path.")
        return question_set

    def _path_for(self, question_set_id: str) -> Path:
        if not isinstance(question_set_id, str) or not _SAFE_IDENTIFIER.fullmatch(question_set_id):
            raise ValueError(
                "Question-set identifiers must use letters, digits, dots, hyphens, or underscores."
            )
        if ".." in question_set_id:
            raise ValueError("Question-set identifiers must not contain parent-directory segments.")
        if self._question_sets.is_symlink():
            raise ValueError("Refusing to use a symbolic-link storage directory.")
        target = self._question_sets / f"{question_set_id}.json"
        if target.parent.resolve() != self._question_sets.resolve():
            raise ValueError("Question-set storage path escaped its root.")
        return target
