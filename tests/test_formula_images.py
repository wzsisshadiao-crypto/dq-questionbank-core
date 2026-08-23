from __future__ import annotations

import base64
import hashlib
import json
import unittest
from pathlib import Path

from dq_questionbank import (
    FormulaImageCandidate,
    Question,
    detect_formula_image_candidates,
    fill_transcription,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "formula-images"


def load_question():
    fixture = json.loads(
        (FIXTURE_DIR / "formula-image-question.json").read_text(encoding="utf-8")
    )
    png = base64.b64decode(fixture["image_png_base64"])
    assert hashlib.sha256(png).hexdigest() == fixture["image_sha256"]
    return Question.from_dict(fixture["question"]), fixture


class DetectionTests(unittest.TestCase):
    def test_flagged_image_binds_to_its_asset_evidence(self):
        question, _ = load_question()
        candidates = detect_formula_image_candidates(question)

        self.assertEqual(1, len(candidates))
        candidate = candidates[0]
        self.assertEqual("q-formula-image-1", candidate.question_id)
        self.assertEqual("stem.blocks[1]", candidate.target_field)
        self.assertEqual("formula-1", candidate.asset_id)
        self.assertEqual("assets/formula-1.png", candidate.asset_uri)
        self.assertEqual(
            "ed68458231f63a4d7664c8f9806447b0e8da1b81ca34ab0dfad1ccc697c2b296",
            candidate.asset_sha256,
        )
        self.assertEqual("", candidate.latex)
        self.assertIsNone(candidate.transcribed_by)
        self.assertEqual("pending", candidate.status)

    def test_unflagged_and_digestless_assets_produce_no_candidates(self):
        question, _ = load_question()
        payload = question.to_dict()
        payload["stem"]["blocks"][1]["metadata"] = {}
        unflagged = Question.from_dict(payload)
        self.assertEqual([], detect_formula_image_candidates(unflagged))

        payload = question.to_dict()
        del payload["assets"][0]["sha256"]
        digestless = Question.from_dict(payload)
        self.assertEqual([], detect_formula_image_candidates(digestless))


class TranscriptionTests(unittest.TestCase):
    def test_filling_records_contributor_and_latex(self):
        question, _ = load_question()
        candidate = detect_formula_image_candidates(question)[0]

        filled = fill_transcription(
            candidate, question, "\\binom{n}{k} = \\frac{n!}{k!(n-k)!}", "tahazarif10"
        )

        self.assertEqual("transcribed", filled.status)
        self.assertEqual("tahazarif10", filled.transcribed_by)
        self.assertIn("\\binom", filled.latex)
        self.assertEqual("formula-1", filled.asset_id, "image stays attached")

    def test_missing_asset_fails_closed(self):
        question, _ = load_question()
        candidate = detect_formula_image_candidates(question)[0]
        payload = question.to_dict()
        payload["assets"] = []
        stripped = Question.from_dict(payload)

        with self.assertRaises(ValueError):
            fill_transcription(candidate, stripped, "x", "someone")

    def test_changed_digest_fails_closed(self):
        question, _ = load_question()
        candidate = detect_formula_image_candidates(question)[0]
        payload = question.to_dict()
        payload["assets"][0]["sha256"] = "0" * 64
        replaced = Question.from_dict(payload)

        with self.assertRaises(ValueError):
            fill_transcription(candidate, replaced, "x", "someone")

    def test_double_transcription_is_rejected(self):
        question, _ = load_question()
        candidate = detect_formula_image_candidates(question)[0]
        filled = fill_transcription(candidate, question, "x+1", "someone")

        with self.assertRaises(ValueError):
            fill_transcription(filled, question, "x+2", "someone-else")


class SerializationTests(unittest.TestCase):
    def test_round_trip_and_unknown_fields_fail_closed(self):
        question, _ = load_question()
        candidate = detect_formula_image_candidates(question)[0]

        restored = FormulaImageCandidate.from_dict(
            json.loads(json.dumps(candidate.to_dict()))
        )
        self.assertEqual(candidate, restored)

        payload = candidate.to_dict()
        payload["mystery"] = True
        with self.assertRaises(ValueError):
            FormulaImageCandidate.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
