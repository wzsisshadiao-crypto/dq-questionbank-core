import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from dq_questionbank_local.case_database import (
    CaseDatabase,
    CaseDatabaseError,
    build_case_database,
    bundled_case_database,
)


ROOT = Path(__file__).resolve().parents[1]


class LocalCaseDatabaseTests(unittest.TestCase):
    def test_bundled_case_is_read_only_and_converts_to_canonical_json(self):
        path = bundled_case_database()
        before = path.read_bytes()
        case = CaseDatabase(path)
        info = case.info()
        payload = case.load()
        self.assertEqual(3, info["question_count"])
        self.assertEqual("synthetic-database-case", payload["id"])
        self.assertEqual(3, len(payload["questions"]))
        self.assertEqual("single_choice", payload["questions"][0]["type"])
        self.assertEqual("C", payload["questions"][0]["answer"]["value"])
        self.assertEqual(before, path.read_bytes())

        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertEqual(
                {"dq_case_metadata", "questions", "question_options", "sqlite_sequence"},
                tables,
            )
            self.assertEqual(0, connection.execute("PRAGMA freelist_count").fetchone()[0])

    def test_builder_reproduces_the_source_semantics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "case.sqlite3"
            build_case_database(ROOT / "examples" / "synthetic-case-source.json", target)
            expected = CaseDatabase(bundled_case_database()).load()
            self.assertEqual(expected, CaseDatabase(target).load())

    def test_rejects_an_unrelated_database(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "unrelated.sqlite3"
            with closing(sqlite3.connect(target)) as connection:
                connection.execute("CREATE TABLE unrelated (value TEXT)")
                connection.commit()
            with self.assertRaises(CaseDatabaseError):
                CaseDatabase(target).info()

    def test_rejects_question_database_without_public_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "missing-metadata.sqlite3"
            with closing(sqlite3.connect(target)) as connection:
                connection.execute(
                    "CREATE TABLE questions (question_id TEXT, subject_attribute TEXT, "
                    "question_type TEXT, body_chinese TEXT)"
                )
                connection.commit()
            with self.assertRaisesRegex(CaseDatabaseError, "license and provenance"):
                CaseDatabase(target).info()
