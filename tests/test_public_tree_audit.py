from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_public_tree.py"
SPEC = importlib.util.spec_from_file_location("audit_public_tree", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PublicTreeAuditTests(unittest.TestCase):
    def test_repository_passes_public_tree_audit(self):
        self.assertEqual(MODULE.audit(), [])

    def test_secret_value_is_reported_without_returning_the_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = "sk-" + "A" * 32
            (root / "config.json").write_text(f'{{"api_key":"{secret}"}}', encoding="utf-8")
            findings = MODULE.audit(root)
            self.assertTrue(findings)
            self.assertNotIn(secret, repr(findings))

    def test_database_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "questions.sqlite3").write_bytes(b"")
            self.assertIn("forbidden file type", {rule for _, rule in MODULE.audit(root)})
