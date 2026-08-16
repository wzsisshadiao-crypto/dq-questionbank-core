from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dq_questionbank import FilesystemStorageAdapter, QuestionSet, StorageAdapter

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "compatibility" / "schema-1.0" / "question-set.json"
)


class FilesystemStorageAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "store"
        self.adapter = FilesystemStorageAdapter(self.root)
        self.question_set = QuestionSet.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_round_trip_uses_deterministic_layout(self):
        self.assertIsInstance(self.adapter, StorageAdapter)
        self.adapter.save(self.question_set)
        target = self.root / "question_sets" / "compatibility-basic.json"
        self.assertTrue(target.is_file())
        first = target.read_bytes()
        self.adapter.save(self.question_set)
        self.assertEqual(first, target.read_bytes())
        self.assertEqual(self.question_set.to_dict(), self.adapter.load(self.question_set.id).to_dict())

    def test_path_traversal_identifiers_fail_closed(self):
        for identifier in ("", "../escape", "..\\escape", "nested/name", ".hidden", "two..dots"):
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError):
                    self.adapter.load(identifier)
        self.assertFalse((self.root.parent / "escape.json").exists())

    def test_atomic_write_keeps_previous_document_when_replace_fails(self):
        self.adapter.save(self.question_set)
        target = self.root / "question_sets" / "compatibility-basic.json"
        original = target.read_bytes()
        changed = QuestionSet.from_dict(self.question_set.to_dict())
        changed.title = "Changed fixture"
        with patch("dq_questionbank.storage.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                self.adapter.save(changed)
        self.assertEqual(original, target.read_bytes())
        self.assertEqual([], list(target.parent.glob("*.tmp")))

    def test_rejects_non_question_set_values(self):
        with self.assertRaises(TypeError):
            self.adapter.save({"id": "not-a-question-set"})
