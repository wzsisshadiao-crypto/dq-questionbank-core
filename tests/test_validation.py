from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank.models import (
    Answer,
    Asset,
    Choice,
    Content,
    ContentBlock,
    Question,
    QuestionSet,
)
from dq_questionbank.validation import validate_question, validate_question_set

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample_questions.json"


def codes(issues):
    return {issue.code for issue in issues}


class ValidationTests(unittest.TestCase):
    def test_sample_is_valid(self):
        sample_set = QuestionSet.from_dict(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))
        self.assertEqual(validate_question_set(sample_set), [])

    def test_choice_answer_must_reference_existing_choice(self):
        question = Question(
            "q1",
            "single_choice",
            Content.text("Choose."),
            choices=[Choice("A", Content.text("One")), Choice("B", Content.text("Two"))],
            answer=Answer("choice", "C"),
        )
        self.assertIn("unknown_choice", codes(validate_question(question)))

    def test_absolute_windows_asset_path_is_rejected(self):
        question = Question(
            "q1",
            "short_answer",
            Content([ContentBlock(type="image", asset_id="image-1")]),
            assets=[Asset("image-1", "image", r"C:\\private\\diagram.png")],
        )
        self.assertIn("unsafe_asset_uri", codes(validate_question(question)))

    def test_parent_traversal_asset_path_is_rejected(self):
        question = Question(
            "q1",
            "short_answer",
            Content([ContentBlock(type="image", asset_id="image-1")]),
            assets=[Asset("image-1", "image", "../private.png")],
        )
        self.assertIn("unsafe_asset_uri", codes(validate_question(question)))

    def test_https_asset_is_allowed(self):
        question = Question(
            "q1",
            "short_answer",
            Content([ContentBlock(type="image", asset_id="image-1")]),
            assets=[Asset("image-1", "image", "https://example.org/original-diagram.png")],
        )
        self.assertNotIn("unsafe_asset_uri", codes(validate_question(question)))

    def test_duplicate_top_level_ids_are_rejected(self):
        question = Question("q1", "short_answer", Content.text("Example"))
        question_set = QuestionSet("set", "Set", [question, question])
        self.assertIn("duplicate_question_id", codes(validate_question_set(question_set)))

    def test_unknown_image_reference_is_rejected(self):
        question = Question(
            "q1", "short_answer", Content([ContentBlock(type="image", asset_id="missing")])
        )
        self.assertIn("unknown_asset", codes(validate_question(question)))
