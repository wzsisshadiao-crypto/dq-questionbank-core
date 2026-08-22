from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank import (
    Answer,
    Choice,
    Content,
    Question,
    QuestionSet,
    SqliteStorageAdapter,
    StorageAdapter,
    validate_with_schema,
)

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "sample_questions.json"


def sample_set(set_id="sqlite-demo"):
    return QuestionSet(
        set_id,
        "Synthetic SQLite demo",
        [
            Question(
                "q-1",
                "single_choice",
                Content.from_dict(
                    {
                        "blocks": [
                            {"type": "text", "text": "Solve "},
                            {"type": "math", "latex": "x + 3 = 7"},
                        ]
                    }
                ),
                choices=[
                    Choice("A", Content.text("3")),
                    Choice("B", Content.text("4")),
                ],
                answer=Answer("choice", "B"),
            )
        ],
    )


class SqliteStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "demo.sqlite3"
        self.storage = SqliteStorageAdapter(self.database_path)

    def tearDown(self):
        self.storage.close()
        self.temporary_directory.cleanup()

    def test_implements_the_public_storage_protocol(self):
        self.assertIsInstance(self.storage, StorageAdapter)

    def test_save_then_load_returns_the_canonical_payload(self):
        question_set = sample_set()
        self.storage.save(question_set)

        restored = self.storage.load("sqlite-demo")

        self.assertEqual(question_set.to_dict(), restored.to_dict())
        self.assertEqual([], validate_with_schema(restored.to_dict()))

    def test_fixture_round_trip_from_the_bundled_sample(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        question_set = QuestionSet.from_dict(payload)

        self.storage.save(question_set)
        restored = self.storage.load(question_set.id)

        self.assertEqual(question_set.to_dict(), restored.to_dict())
        self.assertEqual([], validate_with_schema(restored.to_dict()))

    def test_repeated_saves_are_deterministic(self):
        question_set = sample_set()
        self.storage.save(question_set)
        first = self.storage.load("sqlite-demo").to_dict()

        self.storage.save(question_set)
        second = self.storage.load("sqlite-demo").to_dict()

        self.assertEqual(first, second)
        self.assertEqual(["sqlite-demo"], self.storage.stored_ids())

    def test_saving_an_existing_id_replaces_the_row(self):
        self.storage.save(sample_set("sqlite-demo"))
        replacement = QuestionSet(
            "sqlite-demo",
            "Replacement title",
            [
                Question(
                    "q-replacement",
                    "short_answer",
                    Content.text("What is 2 + 2?"),
                    answer=Answer("text", "4"),
                )
            ],
        )
        self.storage.save(replacement)

        restored = self.storage.load("sqlite-demo")

        self.assertEqual(replacement.to_dict(), restored.to_dict())
        self.assertEqual(["sqlite-demo"], self.storage.stored_ids())

    def test_loading_an_unknown_id_fails_closed(self):
        with self.assertRaises(KeyError):
            self.storage.load("never-saved")

    def test_saving_a_non_question_set_is_rejected(self):
        with self.assertRaises(TypeError):
            self.storage.save({"id": "not-a-question-set"})

    def test_identifiers_are_restricted_like_the_filesystem_adapter(self):
        with self.assertRaises(ValueError):
            self.storage.load("../escape")

    def test_contains_and_stored_ids_report_deterministic_state(self):
        self.assertFalse(self.storage.contains("sqlite-demo"))
        self.storage.save(sample_set("sqlite-demo"))
        self.storage.save(sample_set("sqlite-demo-b"))
        self.assertTrue(self.storage.contains("sqlite-demo"))
        self.assertEqual(["sqlite-demo", "sqlite-demo-b"], self.storage.stored_ids())


class SqliteDemoScriptTests(unittest.TestCase):
    def test_demo_script_round_trips_a_disposable_database(self):
        import subprocess
        import sys as sys_module

        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "demo.sqlite3"
            result = subprocess.run(
                [
                    sys_module.executable,
                    str(Path(__file__).resolve().parents[1] / "examples" / "sqlite_storage_demo.py"),
                    "--db",
                    str(database),
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("round trip validated", result.stdout)


if __name__ == "__main__":
    unittest.main()
