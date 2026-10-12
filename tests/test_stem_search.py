"""Only original synthetic question text is indexed in these tests."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from dq_questionbank_local.stem_search import StemSearchIndex
from dq_questionbank_local.storage import WorkspaceStorage


def sample_payload(set_id="synthetic-set"):
    return {
        "schema_version": "1.0",
        "id": set_id,
        "title": "Synthetic search set",
        "language": "en",
        "questions": [
            {
                "schema_version": "1.0",
                "id": "q-1",
                "type": "short_answer",
                "language": "en",
                "stem": {"blocks": [{"type": "text", "text": "A cobalt compass turns."}]},
            },
            {
                "schema_version": "1.0",
                "id": "q-2",
                "type": "short_answer",
                "language": "en",
                "stem": {"blocks": [{"type": "text", "text": "A compass points north."}]},
            },
        ],
    }


class StemSearchIndexTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.storage = WorkspaceStorage(Path(self.temporary_directory.name))
        self.index = StemSearchIndex(self.storage)
        self.storage.save(sample_payload())

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_fts_phrase_and_rebuildable_sidecar(self):
        result = self.index.search("synthetic-set", "cobalt compass")
        if result["mode"] != "fts5-phrase":
            self.skipTest("SQLite FTS5 is unavailable")
        self.assertEqual(["q-1"], result["ids"])
        self.assertTrue(self.index.path.is_file())
        self.assertEqual([], self.index.search("synthetic-set", "cobal")["ids"])
        # A new server process can use the generated index without changing JSON.
        self.assertEqual(
            ["q-2"], StemSearchIndex(self.storage).search("synthetic-set", "points north")["ids"]
        )

    def test_save_invalidation_replaces_old_stems(self):
        self.index.search("synthetic-set", "cobalt")
        payload = sample_payload()
        payload["questions"][0]["stem"]["blocks"][0]["text"] = "A copper compass turns."
        self.storage.save(payload)
        self.index.invalidate(payload["id"])
        self.assertEqual([], self.index.search("synthetic-set", "cobalt")["ids"])
        self.assertEqual(["q-1"], self.index.search("synthetic-set", "copper")["ids"])

    def test_external_canonical_change_is_reindexed(self):
        first = self.index.search("synthetic-set", "cobalt")
        if first["mode"] != "fts5-phrase":
            self.skipTest("SQLite FTS5 is unavailable")
        payload = sample_payload()
        payload["questions"][1]["stem"]["blocks"][0]["text"] = "A violet compass points north."
        self.storage.save(payload)
        self.assertEqual(["q-2"], self.index.search("synthetic-set", "violet")["ids"])

    def test_missing_fts5_falls_back_to_substring_not_a_false_fts_claim(self):
        with patch("dq_questionbank_local.stem_search.sqlite3.connect") as connect:
            connect.side_effect = sqlite3.OperationalError("no such module: fts5")
            result = self.index.search("synthetic-set", "cobal")
        self.assertEqual({"ids": ["q-1"], "mode": "substring-fallback"}, result)

    def test_operator_like_text_is_literal_and_punctuation_uses_fallback(self):
        self.assertEqual([], self.index.search("synthetic-set", "cobalt OR north")["ids"])
        self.assertEqual("substring-fallback", self.index.search("synthetic-set", "!!!")["mode"])

    def test_rejects_missing_set_and_unbounded_query(self):
        with self.assertRaises(FileNotFoundError):
            self.index.search("missing-set", "cobalt")
        with self.assertRaises(ValueError):
            self.index.search("synthetic-set", "x" * 257)

    def test_sets_do_not_cross_match(self):
        other = sample_payload("second-set")
        other["questions"][0]["stem"]["blocks"][0]["text"] = "An amber marker."
        self.storage.save(other)
        self.assertEqual([], self.index.search("synthetic-set", "amber")["ids"])
        self.assertEqual(["q-1"], self.index.search("second-set", "amber")["ids"])

    def test_removed_canonical_file_discards_its_cached_stems(self):
        self.index.search("synthetic-set", "cobalt")
        if not self.index.path.is_file():
            self.skipTest("SQLite FTS5 is unavailable")
        self.storage.save(sample_payload("second-set"))
        self.storage._path_for("synthetic-set").unlink()
        self.index.search("second-set", "cobalt")
        with closing(sqlite3.connect(self.index.path)) as connection:
            self.assertEqual(
                0,
                connection.execute(
                    "SELECT count(*) FROM stems WHERE set_id = ?", ("synthetic-set",)
                ).fetchone()[0],
            )
