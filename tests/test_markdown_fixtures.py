from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank.formats.markdown import MarkdownImporter

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


if __name__ == "__main__":
    unittest.main()
