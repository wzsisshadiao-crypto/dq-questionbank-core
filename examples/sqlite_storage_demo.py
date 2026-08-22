"""Generate a demo SQLite question database from the synthetic fixture.

This script demonstrates the writable reference ``SqliteStorageAdapter``:
it loads the bundled synthetic fixture, validates it, stores it in a local
SQLite database, loads it back, and re-validates the round trip.

The database file is disposable example output, not a committed artifact.
``.gitignore`` already excludes ``*.db`` / ``*.sqlite3``.

Usage:

    python examples/sqlite_storage_demo.py
    python examples/sqlite_storage_demo.py --db my-demo.sqlite3
    python examples/sqlite_storage_demo.py --source other/questions.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dq_questionbank import QuestionSet, SqliteStorageAdapter, validate_with_schema

DEFAULT_SOURCE = Path(__file__).resolve().parent / "sample_questions.json"
DEFAULT_DB = Path("dq-questionbank-demo.sqlite3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="SQLite database path to create or update (default: %(default)s).",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Canonical JSON question set to store (default: bundled sample).",
    )
    args = parser.parse_args(argv)

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    question_set = QuestionSet.from_dict(payload)
    issues = validate_with_schema(question_set.to_dict())
    if issues:
        for issue in issues:
            print(f"source validation issue: {issue.code}: {issue.message}", file=sys.stderr)
        return 1

    with SqliteStorageAdapter(args.db) as storage:
        storage.save(question_set)
        restored = storage.load(question_set.id)

    issues = validate_with_schema(restored.to_dict())
    if issues or restored.to_dict() != question_set.to_dict():
        print("Round trip failed: restored payload differs from the input.", file=sys.stderr)
        return 1

    print(f"stored {question_set.id}: {len(question_set.questions)} questions")
    print(f"database: {args.db}")
    print("round trip validated through the public validation API")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
