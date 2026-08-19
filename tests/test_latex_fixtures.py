from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank.formats.latex import LatexImporter

FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "community"
    / "tricky-latex-fragment"
)


class LatexFixtureTests(unittest.TestCase):
    def test_tricky_fragment_preserves_unvalidated_formula_source(self):
        imported = LatexImporter().load(FIXTURE_DIR / "source.tex")
        expected = json.loads((FIXTURE_DIR / "expected.json").read_text(encoding="utf-8"))

        self.assertEqual(imported.to_dict(), expected)
        self.assertEqual(imported.questions[0].stem.blocks[1].latex, r"\frac{1}{x+1")


if __name__ == "__main__":
    unittest.main()
