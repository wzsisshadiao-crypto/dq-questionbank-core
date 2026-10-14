from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank.formats.latex import LatexImporter

COMMUNITY_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "community"


class LatexFixtureTests(unittest.TestCase):
    def test_tricky_fragment_preserves_unvalidated_formula_source(self):
        fixture_dir = COMMUNITY_FIXTURES / "tricky-latex-fragment"
        imported = LatexImporter().load(fixture_dir / "source.tex")
        expected = json.loads((fixture_dir / "expected.json").read_text(encoding="utf-8"))

        self.assertEqual(imported.to_dict(), expected)
        self.assertEqual(imported.questions[0].stem.blocks[1].latex, r"\frac{1}{x+1")

    def test_nested_enumerate_items_remain_inside_their_outer_question(self):
        fixture_dir = COMMUNITY_FIXTURES / "nested-latex-enumerate"
        imported = LatexImporter().load(fixture_dir / "source.tex")
        expected = json.loads((fixture_dir / "expected.json").read_text(encoding="utf-8"))

        self.assertEqual(imported.to_dict(), expected)
        self.assertEqual([question.id for question in imported.questions], ["q1", "q2"])


if __name__ == "__main__":
    unittest.main()
