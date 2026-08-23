from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from dq_questionbank import (
    repair_bare_function_names,
    repair_delimiter_spacing,
    repair_latex_braces,
    repair_latex_source,
    repair_operator_spacing,
    validate_with_schema,
)

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / "quality" / "missing-brace-repair"
)

RULE_SET_DIR = Path(__file__).resolve().parent / "fixtures" / "quality" / "rule-set"


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


class LatexRuleSetTests(unittest.TestCase):
    def test_bare_function_names_get_a_backslash(self):
        outcome = repair_bare_function_names("sin x + cos x")

        self.assertTrue(outcome.repaired)
        self.assertEqual(outcome.latex, "\\sin x + \\cos x")
        self.assertEqual(outcome.source, "sin x + cos x")
        self.assertEqual(outcome.rule_id, "latex-bare-function-names")

    def test_bare_function_names_are_idempotent(self):
        outcome = repair_bare_function_names("sin x + cos x")
        second = repair_bare_function_names(outcome.latex)

        self.assertFalse(second.repaired)
        self.assertIsNone(second.finding_code)
        self.assertEqual(second.latex, outcome.latex)

    def test_macro_names_and_longer_words_are_untouched(self):
        latex = "\\sin x + \\cos x + assistant + sinuous"
        outcome = repair_bare_function_names(latex)

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.latex, latex)

    def test_function_names_inside_text_and_macros_are_preserved(self):
        latex = "\\text{sin and cos} + \\mathrm{log} + \\operatorname{inf}"
        outcome = repair_bare_function_names(latex)

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.latex, latex)

    def test_delimiter_spacing_is_normalized(self):
        outcome = repair_delimiter_spacing("\\left( x+1 \\right)^2")

        self.assertTrue(outcome.repaired)
        self.assertEqual(outcome.latex, "\\left(x+1\\right)^2")
        self.assertEqual(outcome.rule_id, "latex-delimiter-spacing")

    def test_delimiter_spacing_is_idempotent(self):
        outcome = repair_delimiter_spacing("\\left( x+1 \\right)")
        second = repair_delimiter_spacing(outcome.latex)

        self.assertFalse(second.repaired)
        self.assertEqual(second.latex, "\\left(x+1\\right)")

    def test_outer_spacing_is_not_delimiter_spacing(self):
        outcome = repair_delimiter_spacing("a + \\left(x+1\\right)")

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.latex, "a + \\left(x+1\\right)")

    def test_operator_spacing_collapses_doubled_spaces(self):
        outcome = repair_operator_spacing("x  +  1 =  y")

        self.assertTrue(outcome.repaired)
        self.assertEqual(outcome.latex, "x + 1 = y")
        self.assertEqual(outcome.rule_id, "latex-operator-spacing")

    def test_operator_spacing_keeps_single_and_missing_spaces(self):
        latex = "x + 1 =y -2 < 3"
        outcome = repair_operator_spacing(latex)

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.latex, latex)

    def test_operator_spacing_preserves_text_regions(self):
        latex = "\\text{a  +  b} + x  -  1"
        outcome = repair_operator_spacing(latex)

        self.assertTrue(outcome.repaired)
        self.assertEqual(outcome.latex, "\\text{a  +  b} + x - 1")

    def test_operator_spacing_is_idempotent(self):
        outcome = repair_operator_spacing("x  =  1")
        second = repair_operator_spacing(outcome.latex)

        self.assertFalse(second.repaired)
        self.assertEqual(second.latex, "x = 1")

    def test_mismatched_delimiters_are_reported_not_repaired(self):
        outcome = repair_latex_source("(x+1]")

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.latex, "(x+1]")
        self.assertEqual(outcome.finding_code, "latex-mismatched-delimiters")
        self.assertTrue(outcome.finding_message)

    def test_unclosed_delimiter_is_reported_not_repaired(self):
        outcome = repair_latex_source("2(x+1")

        self.assertFalse(outcome.repaired)
        self.assertEqual(outcome.finding_code, "latex-mismatched-delimiters")

    def test_escaped_delimiters_do_not_trigger_the_mismatch_finding(self):
        outcome = repair_latex_source("\\(x+1\\)")

        self.assertFalse(outcome.repaired)
        self.assertIsNone(outcome.finding_code)

    def test_rule_set_applies_multiple_rules_in_order(self):
        outcome = repair_latex_source("\\left(  sin x   +   cos x  \\right)")

        self.assertTrue(outcome.repaired)
        self.assertEqual(outcome.latex, "\\left(\\sin x + \\cos x\\right)")
        self.assertEqual(
            outcome.applied_rules,
            (
                "latex-bare-function-names",
                "latex-delimiter-spacing",
                "latex-operator-spacing",
            ),
        )
        self.assertEqual(outcome.source, "\\left(  sin x   +   cos x  \\right)")

    def test_rule_set_composes_with_the_brace_repair(self):
        outcome = repair_latex_source("sin x + cos x \\frac{1}{2")

        self.assertTrue(outcome.repaired)
        self.assertEqual(outcome.latex, "\\sin x + \\cos x \\frac{1}{2}")
        self.assertEqual(
            outcome.applied_rules,
            ("latex-bare-function-names", "latex-missing-closing-brace"),
        )

    def test_rule_set_is_idempotent(self):
        outcome = repair_latex_source("\\left(  sin x   +   cos x  \\right)")
        second = repair_latex_source(outcome.latex)

        self.assertFalse(second.repaired)
        self.assertIsNone(second.finding_code)
        self.assertEqual(second.latex, outcome.latex)

    def test_clean_source_is_returned_unchanged(self):
        outcome = repair_latex_source("\\frac{\\sqrt{3}}{x+1}")

        self.assertFalse(outcome.repaired)
        self.assertIsNone(outcome.finding_code)
        self.assertEqual(outcome.applied_rules, ())

    def test_fixture_rule_set_before_is_transformed_to_after(self):
        before = json.loads((RULE_SET_DIR / "before.json").read_text(encoding="utf-8"))
        after = json.loads((RULE_SET_DIR / "after.json").read_text(encoding="utf-8"))

        repaired = copy.deepcopy(before)
        findings = []
        for question in repaired["questions"]:
            for block in question["stem"]["blocks"]:
                if block["type"] != "math":
                    continue
                outcome = repair_latex_source(block["latex"])
                if outcome.finding_code is not None:
                    findings.append(outcome.finding_code)
                block["latex"] = outcome.latex

        self.assertEqual(repaired, after)
        self.assertEqual([], validate_with_schema(after))
        self.assertEqual(["latex-mismatched-delimiters"], findings)


if __name__ == "__main__":
    unittest.main()
