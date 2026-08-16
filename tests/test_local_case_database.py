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
        self.assertEqual(10, info["question_count"])
        self.assertEqual("synthetic-database-case", payload["id"])
        self.assertEqual(10, len(payload["questions"]))
        self.assertEqual("single_choice", payload["questions"][0]["type"])
        self.assertEqual("en", payload["language"])
        self.assertTrue(all(question["language"] == "en" for question in payload["questions"]))
        first_stem = payload["questions"][0]["stem"]["blocks"]
        self.assertEqual("If x + 4 = 9, what is the value of x?", first_stem[0]["text"])
        self.assertNotIn("\u82e5", str(first_stem))
        self.assertEqual("C", payload["questions"][0]["answer"]["value"])
        self.assertEqual(2023, payload["questions"][0]["source"]["year"])
        group_question = next(
            question for question in payload["questions"] if question["id"] == "DEMO_MATH_004"
        )
        self.assertEqual("DEMO_MATH_004", group_question["id"])
        self.assertFalse(
            any(block.get("language") == "zh-Hans" for block in group_question["stem"]["blocks"])
        )
        table = next(block for block in group_question["stem"]["blocks"] if block["type"] == "table")
        self.assertEqual(9, len(table["rows"]))
        self.assertTrue(all(len(row) == 9 for row in table["rows"]))
        self.assertEqual(["$\\ast$", "$e$", "$p$"], table["rows"][0][:3])
        self.assertTrue(
            all(
                cell.startswith("$") and cell.endswith("$")
                for row in table["rows"]
                for cell in row
            )
        )
        symbols = {cell[1:-1] for cell in table["rows"][0][1:]}
        self.assertEqual(symbols, {row[0][1:-1] for row in table["rows"][1:]})
        for row in table["rows"][1:]:
            self.assertEqual(symbols, {cell[1:-1] for cell in row[1:]})
        for column in range(1, 9):
            self.assertEqual(symbols, {row[column][1:-1] for row in table["rows"][1:]})
        self.assertIn("$(p^3q)(p^2)$", group_question["stem"]["blocks"][-1]["text"])
        self.assertIn("$\\langle p\\rangle$", group_question["answer"]["value"])
        self.assertIn("$C_2 \\times C_2$", group_question["solution"]["blocks"][0]["text"])
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

    def test_rejects_malformed_structured_question_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "case.sqlite3"
            build_case_database(ROOT / "examples" / "synthetic-case-source.json", target)
            with closing(sqlite3.connect(target)) as connection:
                connection.execute(
                    "UPDATE questions SET body_blocks_json = ? WHERE question_id = ?",
                    ("not-json", "DEMO_MATH_004"),
                )
                connection.commit()
            with self.assertRaisesRegex(CaseDatabaseError, "not valid JSON"):
                CaseDatabase(target).load()
