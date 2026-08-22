from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from dq_questionbank import repair_latex_braces, validate_with_schema

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / "quality" / "missing-brace-repair"
)


class LatexBraceRepairTests(unittest.TestCase):
    def test_missing_closing_brace_is_repaired_in_one_step(self):
        outcome = repair_latex_braces("\\frac{\\sqrt{3}}{x+1")

        self.assertTrue(outcome.repaired)
        self.assertEqual(outcome.source, "\\frac{\\sqrt{3}}{x+1")
        self.assertEqual(outcome.latex, "\\frac{\\sqrt{3}}{x+1}")
        self.assertEqual(outcome.rule_id, "latex-missing-closing-brace")
        self.assertIsNone(outcome.finding_code)

    def test_repair_is_idempotent(self):
        outcome = repair_latex_braces("\\frac{\\sqrt{3}}{x+1")
        second = repair_latex_braces(outcome.latex)

        self.assertFalse(second.repaired)
        self.assertIsNone(second.finding_code)
        self.assertEqual(second.latex, outcome.latex)

    def test_escaped_braces_do_not_count(self):
        outcome = repair_latex_braces("\\{x + 1\\}")

        self.assertFalse(outcome.repaired)
        self.assertIsNone(outcome.finding_code)
        self.assertEqual(outcome.latex, "\\{x + 1\\}")

    def test_missing_opening_brace_is_reported_not_repaired(self):
        outcome = repair_latex_braces("\\sqrt 3}")

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.latex, "\\sqrt 3}")
        self.assertEqual(outcome.finding_code, "latex-missing-opening-brace")
        self.assertTrue(outcome.finding_message)

    def test_multiple_breaks_are_reported_not_repaired(self):
        outcome = repair_latex_braces("\\frac{\\sqrt{3}{x+1")

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.latex, "\\frac{\\sqrt{3}{x+1")
        self.assertEqual(outcome.finding_code, "latex-multiple-brace-breaks")

    def test_misordered_braces_are_reported_not_repaired(self):
        outcome = repair_latex_braces("}a{")

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.finding_code, "latex-multiple-brace-breaks")

    def test_trailing_escape_prevents_guessing(self):
        outcome = repair_latex_braces("\\frac{1}{2 \\")

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.latex, "\\frac{1}{2 \\")
        self.assertEqual(outcome.finding_code, "latex-ambiguous-closing-brace")

    def test_fixture_before_is_repaired_to_after_in_one_step(self):
        before = json.loads((FIXTURE_DIR / "before.json").read_text(encoding="utf-8"))
        after = json.loads((FIXTURE_DIR / "after.json").read_text(encoding="utf-8"))

        repaired = copy.deepcopy(before)
        block = repaired["questions"][0]["stem"]["blocks"][1]
        outcome = repair_latex_braces(block["latex"])
        self.assertTrue(outcome.repaired)
        block["latex"] = outcome.latex

        self.assertEqual(repaired, after)
        self.assertEqual([], validate_with_schema(after))


if __name__ == "__main__":
    unittest.main()
