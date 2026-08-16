"""Safe, deterministic local storage for canonical question-set documents."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .validation import validate_question_set

_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class WorkspaceStorage:
    """Store one canonical JSON document per set under a workspace directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser()
        self.question_sets = self.root / "question_sets"
        self._initialize()

    def list_sets(self) -> list[dict[str, Any]]:
        """Return metadata in deterministic id order without exposing full content."""
        entries: list[dict[str, Any]] = []
        for path in sorted(self.question_sets.glob("*.json"), key=lambda item: item.name):
            if path.is_symlink():
                continue
            try:
                payload = self._read_json(path)
                validate_question_set(payload)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            entries.append(
                {
                    "id": payload["id"],
                    "title": payload["title"],
                    "description": payload.get("description", ""),
                    "question_count": len(payload["questions"]),
                }
            )
        return entries

    def load(self, question_set_id: str) -> dict[str, Any]:
        path = self._path_for(question_set_id)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(question_set_id)
        payload = self._read_json(path)
        validate_question_set(payload)
        if payload["id"] != question_set_id:
            raise ValueError("Stored question-set id does not match its filename.")
        return payload

    def contains(self, question_set_id: str) -> bool:
        """Return whether a regular stored document exists for an identifier."""
        path = self._path_for(question_set_id)
        return path.is_file() and not path.is_symlink()

    def save(self, payload: dict[str, Any]) -> None:
        validate_question_set(payload)
        target = self._path_for(payload["id"])
        if target.exists() and target.is_symlink():
            raise ValueError("Refusing to replace a symbolic link.")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{payload['id']}.", suffix=".tmp", dir=self.question_sets
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _initialize(self) -> None:
        if self.root.exists() and self.root.is_symlink():
            raise ValueError("Workspace root must not be a symbolic link.")
        self.root.mkdir(parents=True, exist_ok=True)
        if self.question_sets.exists() and self.question_sets.is_symlink():
            raise ValueError("Workspace question_sets directory must not be a symbolic link.")
        self.question_sets.mkdir(exist_ok=True)

    def _path_for(self, question_set_id: str) -> Path:
        if not isinstance(question_set_id, str) or not _SAFE_IDENTIFIER.fullmatch(question_set_id):
            raise ValueError("Question-set id contains unsafe characters.")
        if ".." in question_set_id:
            raise ValueError("Question-set id must not contain traversal segments.")
        target = self.question_sets / f"{question_set_id}.json"
        if target.parent.resolve() != self.question_sets.resolve():
            raise ValueError("Question-set path escapes the workspace.")
        return target

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Stored document must be a JSON object.")
        return payload
