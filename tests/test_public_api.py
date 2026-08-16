from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_public_api.py"
SPEC = importlib.util.spec_from_file_location("check_public_api", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PublicApiManifestTests(unittest.TestCase):
    def test_checked_in_manifest_matches_stable_api(self):
        self.assertEqual([], MODULE.check_manifest())

    def test_manifest_has_no_process_specific_values(self):
        self.assertNotIn("0x", json.dumps(MODULE.build_manifest()))

    def test_removed_symbol_or_signature_is_detected(self):
        manifest = MODULE.build_manifest()
        manifest["symbols"].pop("QuestionSet")
        manifest["members"]["QuestionSet.to_dict"]["signature"] = "(unexpected)"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            findings = MODULE.check_manifest(path)
        self.assertTrue(any("symbols" in finding for finding in findings))
        self.assertTrue(any("members" in finding for finding in findings))
