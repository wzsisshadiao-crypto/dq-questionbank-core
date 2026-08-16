import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank_local.storage import WorkspaceStorage


def sample_payload(set_id="synthetic-set"):
    return {
        "schema_version": "1.0",
        "id": set_id,
        "title": "Synthetic algebra set",
        "language": "en",
        "questions": [
            {
                "schema_version": "1.0",
                "id": "q-1",
                "type": "short_answer",
                "language": "en",
                "stem": {"blocks": [{"type": "text", "text": "What is 2 plus 2?"}]},
            }
        ],
    }


class LocalWorkspaceStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "workspace"
        self.storage = WorkspaceStorage(self.root)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_round_trip_is_deterministic(self):
        payload = sample_payload()
        self.storage.save(payload)
        target = self.root / "question_sets" / "synthetic-set.json"
        self.assertEqual(payload, self.storage.load("synthetic-set"))
        self.assertEqual(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            target.read_text(encoding="utf-8"),
        )

    def test_rejects_unsafe_identifiers(self):
        for identifier in ("../escape", "..", "with/slash", ""):
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError):
                    self.storage.load(identifier)

    def test_rejects_symbolic_link_target(self):
        target = self.root / "question_sets" / "synthetic-set.json"
        outside = self.root / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        try:
            target.symlink_to(outside)
        except OSError:
            self.skipTest("Symbolic links are unavailable in this environment.")
        with self.assertRaises(ValueError):
            self.storage.save(sample_payload())

    def test_core_validation_rejects_semantically_invalid_import(self):
        payload = sample_payload()
        payload["questions"].append(payload["questions"][0])
        with self.assertRaisesRegex(ValueError, "unique"):
            self.storage.save(payload)
