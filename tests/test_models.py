from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank.models import Content, ContentBlock, Question, QuestionSet

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample_questions.json"


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.sample_set = QuestionSet.from_dict(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))

    def test_question_set_round_trip_is_lossless(self):
        self.assertEqual(
            QuestionSet.from_dict(self.sample_set.to_dict()).to_dict(), self.sample_set.to_dict()
        )

    def test_string_content_is_accepted_for_interoperability(self):
        question = Question.from_dict({"id": "q1", "type": "short_answer", "stem": "Plain stem"})
        self.assertEqual(question.stem.plain_text(), "Plain stem")

    def test_content_renders_math_images_and_tables(self):
        content = Content(
            [
                ContentBlock(type="text", text="Area "),
                ContentBlock(type="math", latex="A=lw"),
                ContentBlock(type="image", asset_id="diagram", alt_text="rectangle"),
                ContentBlock(type="table", rows=[["a", "b"], ["1", "2"]]),
            ]
        )
        self.assertIn("$A=lw$", content.plain_text())
        self.assertIn("[rectangle]", content.plain_text())
        self.assertIn("a | b", content.plain_text())

    def test_single_question_payload_is_wrapped(self):
        question_set = QuestionSet.from_dict(
            {
                "schema_version": "1.0",
                "id": "q1",
                "type": "short_answer",
                "language": "en",
                "stem": {"blocks": [{"type": "text", "text": "Example"}]},
            }
        )
        self.assertEqual([question.id for question in question_set.questions], ["q1"])
