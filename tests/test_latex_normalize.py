from __future__ import annotations

import unittest

from dq_questionbank.latex_normalize import (
    BUILT_IN_RULES,
    GRADE_AUTO_FIXABLE,
    GRADE_REVIEW_REASON,
    LATEX_NORMALIZE_VERSION,
    NormalizationRule,
    NormalizedLatex,
    normalize_latex,
)


def _rule(rule_id: str) -> NormalizationRule:
    return next(rule for rule in BUILT_IN_RULES if rule.id == rule_id)


class AutoFixableRuleTests(unittest.TestCase):
    def test_collapse_space_runs_applies_and_is_idempotent(self):
        outcome = normalize_latex("x +  y   =  z")
        self.assertIn("collapse-space-runs", outcome.applied_rules)
        self.assertEqual(outcome.result, "x + y = z")
        second = normalize_latex(outcome.result)
        self.assertNotIn("collapse-space-runs", second.applied_rules)
        self.assertEqual(second.result, outcome.result)

    def test_collapse_skips_protected_text_regions(self):
        outcome = normalize_latex("\\text{a  b} + c")
        self.assertNotIn("collapse-space-runs", outcome.applied_rules)
        self.assertEqual(outcome.result, "\\text{a  b} + c")

    def test_strip_trailing_space_applies_and_is_idempotent(self):
        outcome = normalize_latex("x + 1   ")
        self.assertIn("strip-trailing-space", outcome.applied_rules)
        self.assertEqual(outcome.result, "x + 1")
        self.assertNotIn(
            "strip-trailing-space", normalize_latex(outcome.result).applied_rules
        )

    def test_inline_dollar_spacing_applies_and_is_idempotent(self):
        outcome = normalize_latex("$ x + 1 $ and $y$")
        self.assertIn("normalize-inline-dollar-spacing", outcome.applied_rules)
        self.assertEqual(outcome.result, "$x + 1$ and $y$")
        self.assertNotIn(
            "normalize-inline-dollar-spacing",
            normalize_latex(outcome.result).applied_rules,
        )

    def test_clean_source_is_unchanged(self):
        outcome = normalize_latex("x + 1 = 2")
        self.assertEqual(outcome.result, "x + 1 = 2")
        self.assertEqual(outcome.applied_rules, ())
        self.assertEqual(outcome.proposals, ())

    def test_rule_ordering_follows_the_registry(self):
        outcome = normalize_latex("$ x $   ")
        order = list(outcome.applied_rules)
        self.assertEqual(
            order,
            sorted(
                order,
                key=lambda item: next(
                    index for index, rule in enumerate(BUILT_IN_RULES) if rule.id == item
                ),
            ),
        )


class ReviewReasonRuleTests(unittest.TestCase):
    def test_double_subscript_proposes_without_editing(self):
        source = "x_{a}_{b} + 1"
        outcome = normalize_latex(source)
        self.assertEqual(outcome.result, source)
        proposal = next(
            item for item in outcome.proposals if item["rule_id"] == "double-subscript-merge"
        )
        self.assertEqual(proposal["grade"], GRADE_REVIEW_REASON)
        self.assertEqual(proposal["current"], source)
        self.assertEqual(proposal["proposed"], "x_{ab} + 1")

    def test_implicit_multiplication_proposes_without_editing(self):
        source = "2x = 6"
        outcome = normalize_latex(source)
        self.assertEqual(outcome.result, source)
        proposal = next(
            item
            for item in outcome.proposals
            if item["rule_id"] == "implicit-multiplication-digit-letter"
        )
        self.assertEqual(proposal["current"], "2x = 6")
        self.assertEqual(proposal["proposed"], "2 \\cdot x = 6")

    def test_malicious_review_rule_cannot_touch_the_result(self):
        malicious = NormalizationRule(
            id="malicious",
            grade=GRADE_REVIEW_REASON,
            explanation="should never run",
            match=lambda latex: True,
            apply=lambda latex: "GARBAGE",
        )
        outcome = normalize_latex("x + 1", (malicious,))
        self.assertEqual(outcome.result, "x + 1")
        self.assertEqual(len(outcome.proposals), 1)
        self.assertEqual(outcome.proposals[0]["proposed"], "GARBAGE")

    def test_proposals_reference_the_original_source(self):
        source = "2x  + 1"
        outcome = normalize_latex(source)
        for proposal in outcome.proposals:
            self.assertEqual(proposal["current"], source)

    def test_combined_run_applies_and_proposes(self):
        outcome = normalize_latex("2x  + 1")
        self.assertIn("collapse-space-runs", outcome.applied_rules)
        self.assertEqual(outcome.result, "2x + 1")
        self.assertTrue(
            any(
                item["rule_id"] == "implicit-multiplication-digit-letter"
                for item in outcome.proposals
            )
        )



class EngineContractTests(unittest.TestCase):
    def test_invalid_grade_is_rejected(self):
        broken = NormalizationRule(
            id="broken",
            grade="maybe",
            explanation="bad grade",
            match=lambda latex: True,
            apply=lambda latex: latex,
        )
        with self.assertRaises(ValueError):
            normalize_latex("x", (broken,))

    def test_rule_subset_selection(self):
        rules = (_rule("strip-trailing-space"),)
        outcome = normalize_latex("x  + 1  ", rules)
        self.assertEqual(outcome.applied_rules, ("strip-trailing-space",))
        self.assertEqual(outcome.result, "x  + 1")

    def test_source_is_always_preserved(self):
        outcome = normalize_latex("$ x $   2y")
        self.assertEqual(outcome.source, "$ x $   2y")
        self.assertNotEqual(outcome.result, outcome.source)

    def test_outcome_round_trip_and_unknown_key_rejection(self):
        outcome = normalize_latex("$ x $   2y")
        payload = outcome.to_dict()
        self.assertEqual(NormalizedLatex.from_dict(payload), outcome)
        payload["note"] = "extra"
        with self.assertRaises(ValueError):
            NormalizedLatex.from_dict(payload)
        bad_proposal = normalize_latex("2x").to_dict()
        bad_proposal["proposals"][0]["extra"] = 1
        with self.assertRaises(ValueError):
            NormalizedLatex.from_dict(bad_proposal)

    def test_rule_serialization_round_trips_through_the_registry(self):
        for rule in BUILT_IN_RULES:
            restored = NormalizationRule.from_dict(rule.to_dict())
            self.assertIs(restored, rule)

    def test_rule_registry_lookup_rejects_unknown_ids(self):
        with self.assertRaises(ValueError):
            NormalizationRule.from_dict(
                {"id": "nope", "grade": GRADE_AUTO_FIXABLE, "explanation": ""}
            )

    def test_rule_registry_lookup_rejects_grade_mismatch(self):
        with self.assertRaises(ValueError):
            NormalizationRule.from_dict(
                {"id": "collapse-space-runs", "grade": GRADE_REVIEW_REASON, "explanation": ""}
            )

    def test_version_is_stable(self):
        self.assertEqual(LATEX_NORMALIZE_VERSION, "latex-normalize/1")
        self.assertEqual(len(BUILT_IN_RULES), 5)
        self.assertEqual(
            [rule.grade for rule in BUILT_IN_RULES[:3]],
            [GRADE_AUTO_FIXABLE] * 3,
        )
        self.assertEqual(
            [rule.grade for rule in BUILT_IN_RULES[3:]],
            [GRADE_REVIEW_REASON] * 2,
        )


if __name__ == "__main__":
    unittest.main()
