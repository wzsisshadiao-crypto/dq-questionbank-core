from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank import (
    AssetRepairProposal,
    Question,
    bind_asset_repair,
    preview_asset_repair,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "asset-repair"


def load_pair():
    fixture = json.loads(
        (FIXTURE_DIR / "asset-repair-pair.json").read_text(encoding="utf-8")
    )
    original = base64.b64decode(fixture["original_png_base64"])
    replacement = base64.b64decode(fixture["replacement_png_base64"])
    assert hashlib.sha256(original).hexdigest() == fixture["original_sha256"]
    assert hashlib.sha256(replacement).hexdigest() == fixture["replacement_sha256"]
    return fixture, original, replacement


def workspace(original: bytes, replacement: bytes):
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    (root / "assets").mkdir()
    (root / "assets" / "diagram-1.png").write_bytes(original)
    (root / "replacements").mkdir()
    (root / "replacements" / "diagram-1-fixed.png").write_bytes(replacement)
    return temporary, root


class BindTests(unittest.TestCase):
    def test_bind_pins_both_digests_and_the_block_path(self):
        fixture, original, replacement = load_pair()
        temporary, root = workspace(original, replacement)
        try:
            question = Question.from_dict(fixture["question"])
            proposal = bind_asset_repair(
                question,
                "stem.blocks[1]",
                "diagram-1",
                "replacements/diagram-1-fixed.png",
                root,
            )

            self.assertEqual("q-asset-repair-1", proposal.question_id)
            self.assertEqual(fixture["original_sha256"], proposal.current_sha256)
            self.assertEqual(fixture["replacement_sha256"], proposal.replacement_sha256)
            self.assertEqual("assets/diagram-1.png", proposal.asset_uri)
        finally:
            temporary.cleanup()

    def test_unknown_asset_and_mismatched_block_fail_closed(self):
        fixture, original, replacement = load_pair()
        temporary, root = workspace(original, replacement)
        try:
            question = Question.from_dict(fixture["question"])
            replacement_path = "replacements/diagram-1-fixed.png"
            with self.assertRaises(ValueError):
                bind_asset_repair(
                    question, "stem.blocks[1]", "unknown-asset", replacement_path, root
                )
            with self.assertRaises(ValueError):
                bind_asset_repair(question, "stem.blocks[0]", "diagram-1", replacement_path, root)
            with self.assertRaises(ValueError):
                bind_asset_repair(question, "stem.blocks[9]", "diagram-1", replacement_path, root)
        finally:
            temporary.cleanup()

    def test_path_traversal_fails_closed(self):
        fixture, original, replacement = load_pair()
        temporary, root = workspace(original, replacement)
        try:
            question = Question.from_dict(fixture["question"])
            for bad in ("../escape.png", "/absolute.png", "a/../../b.png", ""):
                with self.assertRaises(ValueError):
                    bind_asset_repair(question, "stem.blocks[1]", "diagram-1", bad, root)
        finally:
            temporary.cleanup()


class PreviewTests(unittest.TestCase):
    def test_preview_reports_both_digests_without_writing(self):
        fixture, original, replacement = load_pair()
        temporary, root = workspace(original, replacement)
        try:
            question = Question.from_dict(fixture["question"])
            proposal = bind_asset_repair(
                question, "stem.blocks[1]", "diagram-1", "replacements/diagram-1-fixed.png", root
            )

            preview = preview_asset_repair(proposal, question, root)

            self.assertEqual(fixture["original_sha256"], preview["current_sha256"])
            self.assertEqual(fixture["replacement_sha256"], preview["replacement_sha256"])
            self.assertEqual(67, preview["replacement_bytes"])
            self.assertFalse(preview["applied"])
            self.assertEqual(
                original,
                (root / "assets" / "diagram-1.png").read_bytes(),
                "preview never overwrites the bound asset",
            )
        finally:
            temporary.cleanup()

    def test_current_digest_drift_fails_closed(self):
        fixture, original, replacement = load_pair()
        temporary, root = workspace(original, replacement)
        try:
            question = Question.from_dict(fixture["question"])
            proposal = bind_asset_repair(
                question, "stem.blocks[1]", "diagram-1", "replacements/diagram-1-fixed.png", root
            )
            payload = question.to_dict()
            payload["assets"][0]["sha256"] = "0" * 64
            drifted = Question.from_dict(payload)

            with self.assertRaises(ValueError):
                preview_asset_repair(proposal, drifted, root)
        finally:
            temporary.cleanup()

    def test_replacement_bytes_drift_fails_closed(self):
        fixture, original, replacement = load_pair()
        temporary, root = workspace(original, replacement)
        try:
            question = Question.from_dict(fixture["question"])
            proposal = bind_asset_repair(
                question, "stem.blocks[1]", "diagram-1", "replacements/diagram-1-fixed.png", root
            )
            (root / "replacements" / "diagram-1-fixed.png").write_bytes(b"tampered")

            with self.assertRaises(ValueError):
                preview_asset_repair(proposal, question, root)
        finally:
            temporary.cleanup()


class SerializationTests(unittest.TestCase):
    def test_round_trip_and_unknown_fields_fail_closed(self):
        fixture, original, replacement = load_pair()
        temporary, root = workspace(original, replacement)
        try:
            question = Question.from_dict(fixture["question"])
            proposal = bind_asset_repair(
                question, "stem.blocks[1]", "diagram-1", "replacements/diagram-1-fixed.png", root
            )

            restored = AssetRepairProposal.from_dict(
                json.loads(json.dumps(proposal.to_dict()))
            )
            self.assertEqual(proposal, restored)

            payload = proposal.to_dict()
            payload["mystery"] = True
            with self.assertRaises(ValueError):
                AssetRepairProposal.from_dict(payload)
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
