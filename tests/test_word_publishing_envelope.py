from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "word-publishing" / "synthetic-envelope.json"


class WordPublishingEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.envelope = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_synthetic_envelope_has_deterministic_contract_shape(self):
        self.assertEqual(self.envelope["envelope_version"], "0.1")
        self.assertEqual(self.envelope["mode"], "compose")
        self.assertEqual(self.envelope["blocks"][0]["block_id"], "block-q-001")
        self.assertRegex(
            self.envelope["blocks"][0]["question_fingerprint"],
            r"^sha256:[0-9a-f]{64}$",
        )
        canonical = json.dumps(
            self.envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(
            hashlib.sha256(canonical.encode()).hexdigest(),
            "a4588923cfaa5f6bfa1f14e54c296c91c4045cce405fec60eeea16122ae07be8",
        )

    def test_reference_envelope_is_loopback_only_and_never_uses_credentials(self):
        origin = urlparse(self.envelope["service_origin"])
        self.assertEqual(origin.scheme, "http")
        self.assertIn(origin.hostname, {"127.0.0.1", "localhost", "::1"})
        self.assertEqual(
            self.envelope["security"]["allowed_origins"],
            [self.envelope["service_origin"]],
        )
        self.assertEqual(self.envelope["security"]["remote_origins"], [])
        self.assertEqual(self.envelope["security"]["credentials"], "never")

    def test_refresh_and_rollback_are_explicit_stale_safe_policies(self):
        self.assertEqual(self.envelope["refresh"]["strategy"], "explicit")
        self.assertEqual(self.envelope["refresh"]["on_missing"], "stale")
        self.assertEqual(self.envelope["refresh"]["on_revision_mismatch"], "stale")
        self.assertEqual(self.envelope["rollback"]["scope"], "single-block")
        self.assertEqual(self.envelope["rollback"]["on_failure"], "restore-previous-block")


if __name__ == "__main__":
    unittest.main()
