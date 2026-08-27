from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from wiki_sync import check_manifest, check_wiki, export_wiki, sync_wiki  # noqa: E402


class WikiSyncTests(unittest.TestCase):
    def test_canonical_source_manifest_is_current(self):
        self.assertEqual(check_manifest(), [])

    def test_export_check_and_sync_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temp_name:
            destination = Path(temp_name) / "wiki"
            exported = export_wiki(destination)
            self.assertEqual(len(exported), 11)
            self.assertEqual(check_wiki(destination), [])

            changed = destination / "Home.md"
            changed.write_text("stale", encoding="utf-8")
            self.assertEqual(check_wiki(destination), ["Stale Wiki page: Home.md"])
            self.assertEqual(sync_wiki(destination), ("Home.md",))
            self.assertEqual(check_wiki(destination), [])

    def test_sync_does_not_delete_extra_pages(self):
        with tempfile.TemporaryDirectory() as temp_name:
            destination = Path(temp_name) / "wiki"
            export_wiki(destination)
            extra = destination / "Local-Notes.md"
            extra.write_text("Keep this file", encoding="utf-8")
            self.assertEqual(sync_wiki(destination), ())
            self.assertTrue(extra.exists())
            self.assertEqual(check_wiki(destination), ["Extra Wiki page: Local-Notes.md"])
