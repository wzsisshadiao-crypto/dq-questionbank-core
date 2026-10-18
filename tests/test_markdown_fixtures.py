from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank.formats.markdown import MarkdownExporter, MarkdownImporter
from dq_questionbank.models import QuestionSet

COMMUNITY_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "community"


class MarkdownFixtureTests(unittest.TestCase):
    def test_commonmark_indented_choices_remain_canonical_choices(self):
        fixture_dir = COMMUNITY_FIXTURES / "markdown-indented-choices"
        imported = MarkdownImporter().load(fixture_dir / "source.md")
        expected = json.loads((fixture_dir / "expected.json").read_text(encoding="utf-8"))

        self.assertEqual(imported.to_dict(), expected)
        self.assertEqual(
            [choice.id for choice in imported.questions[0].choices],
            ["A", "B", "C"],
        )

    def test_reserved_headings_in_content_round_trip_as_literal_text(self):
        fixture_dir = COMMUNITY_FIXTURES / "markdown-reserved-headings"
        question_set = QuestionSet.from_dict(
            json.loads((fixture_dir / "canonical.json").read_text(encoding="utf-8"))
        )

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "reserved-headings.md"
            MarkdownExporter().dump(question_set, target)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                (fixture_dir / "expected.md").read_text(encoding="utf-8"),
            )
            imported = MarkdownImporter().load(target)

        self.assertEqual(imported.to_dict(), question_set.to_dict())
        self.assertIsNone(imported.questions[0].solution)

    def test_answer_markers_in_content_round_trip_as_literal_text(self):
        fixture_dir = COMMUNITY_FIXTURES / "markdown-answer-marker"
        question_set = QuestionSet.from_dict(
            json.loads((fixture_dir / "canonical.json").read_text(encoding="utf-8"))
        )

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "answer-marker.md"
            MarkdownExporter().dump(question_set, target)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                (fixture_dir / "expected.md").read_text(encoding="utf-8"),
            )
            imported = MarkdownImporter().load(target)

        self.assertEqual(imported.to_dict(), question_set.to_dict())
        self.assertIsNone(imported.questions[0].answer)


if __name__ == "__main__":
    unittest.main()
