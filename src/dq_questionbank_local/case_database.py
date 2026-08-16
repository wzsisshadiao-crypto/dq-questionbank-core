"""Read-only adapter and builder for reviewed public SQLite cases."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .validation import validate_question_set

_REQUIRED_QUESTION_COLUMNS = {
    "question_id",
    "subject_attribute",
    "question_type",
    "body_chinese",
}
_CANONICAL_TYPES = {
    "single_choice",
    "multiple_choice",
    "true_false",
    "fill_blank",
    "short_answer",
    "essay",
    "composite",
}
_MAX_CASE_QUESTIONS = 2_000


class CaseDatabaseError(ValueError):
    """Raised when a database is not a safe, supported public case."""


class CaseDatabase:
    """Convert a reviewed question-bank SQLite case to canonical JSON."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser()

    def info(self) -> dict[str, Any]:
        try:
            with closing(self._connect()) as connection:
                self._validate_schema(connection)
                count = int(connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
                metadata = self._metadata(connection)
        except sqlite3.Error as exc:
            raise CaseDatabaseError("Case database is not a readable SQLite document.") from exc
        return self._public_info(metadata, count)

    def load(self) -> dict[str, Any]:
        try:
            with closing(self._connect()) as connection:
                self._validate_schema(connection)
                metadata = self._metadata(connection)
                count = int(connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
                info = self._public_info(metadata, count)
                if count > _MAX_CASE_QUESTIONS:
                    raise CaseDatabaseError(
                        f"Public database cases are limited to {_MAX_CASE_QUESTIONS} questions."
                    )
                rows = connection.execute("SELECT * FROM questions ORDER BY question_id").fetchall()
                options = self._options_by_question(connection)
        except sqlite3.Error as exc:
            raise CaseDatabaseError("Case database is not a readable SQLite document.") from exc

        payload = {
            "schema_version": "1.0",
            "id": info["id"],
            "title": info["title"],
            "description": info["description"],
            "language": info["language"],
            "metadata": {
                "database_case": True,
                "license": info["license"],
                "provenance": info["provenance"],
            },
            "questions": [
                self._convert_question(dict(row), options.get(row["question_id"], []), info)
                for row in rows
            ],
        }
        return validate_question_set(payload)

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file() or self.path.is_symlink():
            raise CaseDatabaseError("Case database must be a regular local file.")
        resolved = self.path.resolve().as_posix()
        uri = f"file:{quote(resolved, safe='/:')}?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=2)
        except sqlite3.Error as exc:
            raise CaseDatabaseError("Case database could not be opened read-only.") from exc
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    @staticmethod
    def _public_info(metadata: dict[str, str], count: int) -> dict[str, Any]:
        return {
            "id": metadata["case_id"],
            "title": metadata["title"],
            "description": metadata["description"],
            "language": metadata["language"],
            "license": metadata["license"],
            "provenance": metadata["provenance"],
            "question_count": count,
        }

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "questions" not in tables:
            raise CaseDatabaseError("Case database has no questions table.")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(questions)")}
        if _REQUIRED_QUESTION_COLUMNS - columns:
            raise CaseDatabaseError("Case database questions table is missing required public fields.")

    @staticmethod
    def _metadata(connection: sqlite3.Connection) -> dict[str, str]:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'dq_case_metadata'"
        ).fetchone()
        if not exists:
            raise CaseDatabaseError("Public case database has no license and provenance metadata.")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(dq_case_metadata)")}
        expected = {"case_id", "title", "description", "language", "license", "provenance"}
        if not expected.issubset(columns):
            raise CaseDatabaseError("Case metadata is incomplete.")
        row = connection.execute(
            "SELECT case_id, title, description, language, license, provenance "
            "FROM dq_case_metadata LIMIT 1"
        ).fetchone()
        if not row or any(not str(value or "").strip() for value in row):
            raise CaseDatabaseError("Case metadata must contain non-empty public values.")
        return dict(row)

    @staticmethod
    def _options_by_question(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'question_options'"
        ).fetchone()
        if not exists:
            return {}
        columns = {row[1] for row in connection.execute("PRAGMA table_info(question_options)")}
        required = {"question_id", "option_label", "option_chinese", "option_english", "is_correct"}
        if not required.issubset(columns):
            raise CaseDatabaseError("Case database options table is missing required public fields.")
        grouped: dict[str, list[dict[str, Any]]] = {}
        rows = connection.execute(
            "SELECT question_id, option_label, option_chinese, option_english, is_correct "
            "FROM question_options ORDER BY question_id, option_label"
        ).fetchall()
        for row in rows:
            grouped.setdefault(row["question_id"], []).append(dict(row))
        return grouped

    def _convert_question(
        self,
        row: dict[str, Any],
        option_rows: list[dict[str, Any]],
        case_info: dict[str, Any],
    ) -> dict[str, Any]:
        question_type = self._question_type(row.get("question_format"), option_rows)
        question: dict[str, Any] = {
            "schema_version": "1.0",
            "id": str(row["question_id"]),
            "type": question_type,
            "language": "zh-Hans" if row.get("body_chinese") else "en",
            "subject": str(row.get("subject_attribute") or "General"),
            "stem": _bilingual_content(row.get("body_chinese"), row.get("body_english")),
            "metadata": {
                "database_case": True,
                "original_question_type": row.get("question_type"),
            },
        }
        for key in ("grade", "question_category"):
            if row.get(key):
                question["metadata"][key] = row[key]

        choices = [
            {
                "id": str(option["option_label"]),
                "content": _bilingual_content(
                    option.get("option_chinese"), option.get("option_english")
                ),
            }
            for option in option_rows
        ]
        if choices:
            question["choices"] = choices

        correct = [str(option["option_label"]) for option in option_rows if option.get("is_correct")]
        if correct:
            question["answer"] = {
                "kind": "choices" if len(correct) > 1 else "choice",
                "value": correct if len(correct) > 1 else correct[0],
            }
        elif row.get("answer_chinese") or row.get("answer_english"):
            answer = str(row.get("answer_chinese") or row.get("answer_english"))
            alternatives = [str(row["answer_english"])] if row.get("answer_english") else []
            question["answer"] = {"kind": "text", "value": answer}
            if alternatives and alternatives[0] != answer:
                question["answer"]["alternatives"] = alternatives

        solution_chinese = row.get("solutions_chinese") or row.get("analysis_chinese")
        solution_english = row.get("solutions_english") or row.get("analysis_english")
        if solution_chinese or solution_english:
            question["solution"] = _bilingual_content(solution_chinese, solution_english)

        source_title = row.get("source_chinese") or row.get("source_english")
        if source_title:
            question["source"] = {
                "title": str(source_title),
                "license": case_info["license"],
                "attribution": case_info["provenance"],
            }
        return question

    @staticmethod
    def _question_type(question_format: Any, option_rows: list[dict[str, Any]]) -> str:
        normalized = str(question_format or "").strip()
        if normalized in _CANONICAL_TYPES:
            return normalized
        if option_rows:
            correct_count = sum(bool(option.get("is_correct")) for option in option_rows)
            return "multiple_choice" if correct_count > 1 else "single_choice"
        mappings = {
            "\u5224\u65ad\u9898": "true_false",
            "\u586b\u7a7a\u9898": "fill_blank",
            "\u7b80\u7b54\u9898": "short_answer",
            "\u89e3\u7b54\u9898": "short_answer",
            "\u8bba\u8ff0\u9898": "essay",
        }
        return mappings.get(normalized, "short_answer")


def bundled_case_database() -> Path:
    """Return the reviewed synthetic database shipped with the package."""
    resource = files("dq_questionbank_local").joinpath("data", "synthetic-case.sqlite3")
    return Path(str(resource))


def build_case_database(source: Path, target: Path) -> None:
    """Build a public case database atomically from an auditable JSON source."""
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    case = data.get("case")
    questions = data.get("questions")
    if not isinstance(case, dict) or not isinstance(questions, list):
        raise CaseDatabaseError("Case source must contain case metadata and questions.")
    required_metadata = {"case_id", "title", "description", "language", "license", "provenance"}
    if any(not str(case.get(key, "")).strip() for key in required_metadata):
        raise CaseDatabaseError("Case source metadata is incomplete.")

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}.", suffix=".sqlite3.tmp", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA application_id = 0x44514342")
            connection.execute("PRAGMA user_version = 1")
            _create_case_schema(connection)
            metadata_columns = (
                "case_id", "title", "description", "language", "license", "provenance"
            )
            connection.execute(
                "INSERT INTO dq_case_metadata "
                "(case_id, title, description, language, license, provenance) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                tuple(case[key] for key in metadata_columns),
            )
            for question in questions:
                _insert_case_question(connection, question)
            connection.commit()
        finally:
            connection.close()
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _create_case_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE dq_case_metadata (
            case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            language TEXT NOT NULL,
            license TEXT NOT NULL,
            provenance TEXT NOT NULL
        );
        CREATE TABLE questions (
            question_id TEXT PRIMARY KEY,
            subject_attribute TEXT NOT NULL,
            grade TEXT,
            question_type TEXT NOT NULL,
            question_format TEXT,
            question_category TEXT,
            source_chinese TEXT,
            source_english TEXT,
            body_chinese TEXT NOT NULL,
            body_english TEXT,
            answer_chinese TEXT,
            answer_english TEXT,
            analysis_chinese TEXT,
            analysis_english TEXT,
            solutions_chinese TEXT,
            solutions_english TEXT
        );
        CREATE TABLE question_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT NOT NULL,
            option_label TEXT NOT NULL,
            option_chinese TEXT,
            option_english TEXT,
            is_correct INTEGER NOT NULL DEFAULT 0 CHECK (is_correct IN (0, 1)),
            FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
            UNIQUE (question_id, option_label)
        );
        CREATE INDEX idx_case_questions_subject ON questions(subject_attribute);
        CREATE INDEX idx_case_options_question ON question_options(question_id);
        """
    )


def _insert_case_question(connection: sqlite3.Connection, question: Any) -> None:
    if not isinstance(question, dict):
        raise CaseDatabaseError("Every case question must be an object.")
    required = {"question_id", "subject_attribute", "question_type", "body_chinese"}
    if any(not str(question.get(key, "")).strip() for key in required):
        raise CaseDatabaseError("A case question is missing a required public field.")
    columns = (
        "question_id", "subject_attribute", "grade", "question_type", "question_format",
        "question_category", "source_chinese", "source_english", "body_chinese", "body_english",
        "answer_chinese", "answer_english", "analysis_chinese", "analysis_english",
        "solutions_chinese", "solutions_english",
    )
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO questions ({', '.join(columns)}) VALUES ({placeholders})",
        tuple(question.get(column) for column in columns),
    )
    for option in question.get("options", []):
        connection.execute(
            "INSERT INTO question_options "
            "(question_id, option_label, option_chinese, option_english, is_correct) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                question["question_id"],
                option.get("option_label"),
                option.get("option_chinese"),
                option.get("option_english"),
                1 if option.get("is_correct") else 0,
            ),
        )


def _bilingual_content(chinese: Any, english: Any) -> dict[str, list[dict[str, Any]]]:
    blocks: list[dict[str, Any]] = []
    if chinese:
        blocks.append({"type": "text", "text": str(chinese), "language": "zh-Hans"})
    if chinese and english and english != chinese:
        blocks.append({"type": "line_break"})
    if english and english != chinese:
        blocks.append({"type": "text", "text": str(english), "language": "en"})
    return {"blocks": blocks}
