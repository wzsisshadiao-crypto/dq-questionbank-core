from __future__ import annotations

import copy
import json
import unittest

from dq_questionbank import (
    RULESET_VERSION,
    Answer,
    Content,
    ContentBlock,
    QualityFinding,
    Question,
    field_fingerprint,
    finding_state,
)
from dq_questionbank.math_consistency import (
    MATH_CONSISTENCY_VERSION,
    MAX_ABS_VALUE,
    MAX_SUM_TERMS,
    RULE_ARITHMETIC_MISMATCH,
    ArithmeticCheckReport,
    ArithmeticSkip,
    check_arithmetic,
)


def make_question(latex_blocks, answer=None, question_id="q-math-1"):
    blocks = [ContentBlock(type="math", latex=latex) for latex in latex_blocks]
    return Question(question_id, "short_answer", Content(blocks), answer=answer)


def text_answer(value):
    return Answer(kind="text", value=value)


def skip_pairs(report):
    return [(skip.locator, skip.reason) for skip in report.skipped]


class ContractTests(unittest.TestCase):
    def test_module_constants_match_the_issue_contract(self):
        self.assertEqual("math-consistency/1", MATH_CONSISTENCY_VERSION)
        self.assertEqual("arithmetic-mismatch", RULE_ARITHMETIC_MISMATCH)
        self.assertEqual(1000, MAX_SUM_TERMS)
        self.assertEqual(10**12, MAX_ABS_VALUE)


class ConsistentPairTests(unittest.TestCase):
    def test_consistent_string_answer_produces_no_finding(self):
        report = check_arithmetic(make_question(["3+4*2"], text_answer("11")))

        self.assertEqual((), report.findings)
        self.assertEqual((), report.skipped)

    def test_consistent_plain_number_answers(self):
        for value in (11, 11.0):
            with self.subTest(value=value):
                report = check_arithmetic(make_question(["3+4*2"], text_answer(value)))

                self.assertEqual((), report.findings)
                self.assertEqual((), report.skipped)

    def test_float_noise_stays_within_relative_tolerance(self):
        report = check_arithmetic(make_question(["0.1+0.2"], text_answer("0.3")))

        self.assertEqual((), report.findings)
        self.assertEqual((), report.skipped)

    def test_single_surrounding_delimiters_are_stripped(self):
        for latex in (r"\[3+4*2\]", r"\(3+4*2\)", "$3+4*2$"):
            with self.subTest(latex=latex):
                report = check_arithmetic(make_question([latex], text_answer("11")))

                self.assertEqual((), report.findings)
                self.assertEqual((), report.skipped)


class InconsistentPairTests(unittest.TestCase):
    def test_inconsistent_answer_reports_both_computed_values(self):
        question = make_question(["3+4*2"], text_answer("14"))
        report = check_arithmetic(question)

        self.assertEqual(1, len(report.findings))
        finding = report.findings[0]
        self.assertEqual("q-math-1", finding.question_id)
        self.assertEqual("stem.blocks[0]", finding.target_field)
        self.assertEqual(RULE_ARITHMETIC_MISMATCH, finding.rule_id)
        self.assertEqual("arithmetic-mismatch", finding.rule_id)
        self.assertEqual(RULESET_VERSION, finding.ruleset_version)
        self.assertEqual("quality/1", finding.ruleset_version)
        self.assertEqual("warning", finding.severity)
        self.assertIn("computes 11", finding.explanation)
        self.assertIn("answer says 14", finding.explanation)
        self.assertEqual((), report.skipped)

    def test_findings_are_current_quality_findings(self):
        question = make_question(["3+4*2"], text_answer("14"))

        finding = check_arithmetic(question).findings[0]

        self.assertIsInstance(finding, QualityFinding)
        self.assertEqual("current", finding_state(finding, question))

    def test_fingerprints_follow_quality_conventions(self):
        question = make_question(["3+4*2"], text_answer("14"))

        finding = check_arithmetic(question).findings[0]

        expected = {
            "stem.blocks[0]": field_fingerprint(question.stem.blocks[0].to_dict()),
            "answer": field_fingerprint(question.answer.to_dict()),
        }
        self.assertEqual(expected, dict(finding.input_fingerprints))

    def test_every_evaluable_block_is_compared_independently(self):
        question = make_question(["3+4*2", "x+1"], text_answer("14"))
        report = check_arithmetic(question)

        self.assertEqual(1, len(report.findings))
        self.assertEqual("stem.blocks[0]", report.findings[0].target_field)
        self.assertEqual([("stem/blocks/1", "free-variables")], skip_pairs(report))


class PrecedenceTests(unittest.TestCase):
    def test_multiplication_binds_tighter_than_addition(self):
        consistent = check_arithmetic(make_question(["2+3*4"], text_answer("14")))
        self.assertEqual((), consistent.findings)

        finding = check_arithmetic(
            make_question(["2+3*4"], text_answer("20"))
        ).findings[0]
        self.assertIn("computes 14", finding.explanation)

    def test_exponentiation_is_right_associative(self):
        consistent = check_arithmetic(make_question(["2^3^2"], text_answer("512")))
        self.assertEqual((), consistent.findings)

        finding = check_arithmetic(
            make_question(["2^3^2"], text_answer("64"))
        ).findings[0]
        self.assertIn("computes 512", finding.explanation)

    def test_unary_minus_binds_looser_than_exponentiation(self):
        consistent = check_arithmetic(make_question(["-2^2"], text_answer("-4")))
        self.assertEqual((), consistent.findings)

        finding = check_arithmetic(
            make_question(["-2^2"], text_answer("4"))
        ).findings[0]
        self.assertIn("computes -4", finding.explanation)


class SkippedExpressionTests(unittest.TestCase):
    def test_free_variables_take_precedence_over_other_reasons(self):
        report = check_arithmetic(make_question(["x+1"], text_answer("5")))

        self.assertEqual([("stem/blocks/0", "free-variables")], skip_pairs(report))
        self.assertEqual((), report.findings)

    def test_sum_notation_with_a_bound_variable_is_skipped(self):
        report = check_arithmetic(
            make_question([r"\sum_{i=1}^{4} i"], text_answer("10"))
        )

        self.assertEqual([("stem/blocks/0", "free-variables")], skip_pairs(report))
        self.assertEqual((), report.findings)

    def test_macros_with_letters_report_free_variables_first(self):
        report = check_arithmetic(make_question([r"\frac{3}{4}"], text_answer("0.75")))

        self.assertEqual([("stem/blocks/0", "free-variables")], skip_pairs(report))
        self.assertEqual((), report.findings)

    def test_braces_and_other_symbols_are_unparseable(self):
        for latex in ("{3+4}", "3 = 4", "3 \\ 4"):
            with self.subTest(latex=latex):
                report = check_arithmetic(make_question([latex], text_answer("7")))

                self.assertEqual(
                    [("stem/blocks/0", "unparseable-expression")], skip_pairs(report)
                )
                self.assertEqual((), report.findings)

    def test_structurally_broken_expressions_are_unparseable(self):
        for latex in ("(3+4", "3 +", ""):
            with self.subTest(latex=latex):
                report = check_arithmetic(make_question([latex], text_answer("7")))

                self.assertEqual(
                    [("stem/blocks/0", "unparseable-expression")], skip_pairs(report)
                )
                self.assertEqual((), report.findings)

    def test_division_by_zero_is_skipped(self):
        for latex in ("1/0", "1/(2-2)"):
            with self.subTest(latex=latex):
                report = check_arithmetic(make_question([latex], text_answer("7")))

                self.assertEqual(
                    [("stem/blocks/0", "division-by-zero")], skip_pairs(report)
                )
                self.assertEqual((), report.findings)

    def test_magnitude_guard_skips_huge_values(self):
        cases = ("10^13", "2^100", "2^999999999", "999999999999 * 999999999999")
        for latex in cases:
            with self.subTest(latex=latex):
                report = check_arithmetic(make_question([latex], text_answer("1")))

                self.assertEqual(
                    [("stem/blocks/0", "magnitude-exceeded")], skip_pairs(report)
                )
                self.assertEqual((), report.findings)

    def test_stem_without_math_blocks_reports_no_numeric_expressions(self):
        question = Question(
            "q-plain",
            "short_answer",
            Content([ContentBlock(type="text", text="No formulas here.")]),
            answer=text_answer("11"),
        )
        report = check_arithmetic(question)

        self.assertEqual((), report.findings)
        self.assertEqual([("stem", "no-numeric-expressions")], skip_pairs(report))


class BoundedSumTests(unittest.TestCase):
    def test_ellipsis_sum_within_bounds_evaluates(self):
        cases = (
            (r"1 + 2 + 3 + \cdots + 100", "5050"),
            ("1 + 2 + 3 + ... + 10", "55"),
        )
        for latex, value in cases:
            with self.subTest(latex=latex):
                report = check_arithmetic(make_question([latex], text_answer(value)))

                self.assertEqual((), report.findings)
                self.assertEqual((), report.skipped)

    def test_descending_progression_evaluates(self):
        report = check_arithmetic(
            make_question([r"10 + 8 + 6 + \cdots + 2"], text_answer("30"))
        )

        self.assertEqual((), report.findings)
        self.assertEqual((), report.skipped)

    def test_sum_exceeding_the_term_cap_is_skipped(self):
        report = check_arithmetic(
            make_question([r"1 + 2 + 3 + \cdots + 2000"], text_answer("2001000"))
        )

        self.assertEqual([("stem/blocks/0", "sum-terms-exceeded")], skip_pairs(report))
        self.assertEqual((), report.findings)

    def test_non_arithmetic_progression_is_skipped(self):
        report = check_arithmetic(
            make_question([r"2 + 4 + 8 + \cdots + 1024"], text_answer("2034"))
        )

        self.assertEqual(
            [("stem/blocks/0", "unparseable-expression")], skip_pairs(report)
        )
        self.assertEqual((), report.findings)


class AnswerSideTests(unittest.TestCase):
    def test_non_numeric_answers_are_skipped(self):
        cases = (
            ("missing", None),
            ("prose", text_answer("blue")),
            ("free-variable", text_answer("y+2")),
            ("other-kind", Answer(kind="fraction", value="7/2")),
            ("none-value", text_answer(None)),
            ("boolean", text_answer(True)),
        )
        for label, answer in cases:
            with self.subTest(label=label):
                report = check_arithmetic(make_question(["3+4*2"], answer))

                self.assertEqual((), report.findings)
                self.assertEqual([("answer", "non-numeric-answer")], skip_pairs(report))

    def test_answer_side_guards_report_the_answer_locator(self):
        huge = check_arithmetic(make_question(["3+4*2"], text_answer(10**13)))
        self.assertEqual([("answer", "magnitude-exceeded")], skip_pairs(huge))

        zero = check_arithmetic(make_question(["3+4*2"], text_answer("5/0")))
        self.assertEqual([("answer", "division-by-zero")], skip_pairs(zero))


class ReportContractTests(unittest.TestCase):
    def test_report_round_trips_through_json(self):
        question = make_question(["3+4*2", "x+1"], text_answer("14"))
        report = check_arithmetic(question)

        self.assertEqual(1, len(report.findings))
        self.assertEqual(1, len(report.skipped))
        payload = json.loads(json.dumps(report.to_dict()))
        restored = ArithmeticCheckReport.from_dict(payload)

        self.assertEqual(report, restored)
        self.assertIsInstance(restored.findings[0], QualityFinding)
        self.assertIsInstance(restored.skipped[0], ArithmeticSkip)

    def test_skip_round_trips_through_its_serialized_form(self):
        skip = ArithmeticSkip(locator="stem/blocks/2", reason="free-variables")

        payload = json.loads(json.dumps(skip.to_dict()))

        self.assertEqual(skip, ArithmeticSkip.from_dict(payload))

    def test_unknown_report_and_skip_keys_fail_closed(self):
        with self.assertRaises(ValueError):
            ArithmeticCheckReport.from_dict(
                {"findings": [], "skipped": [], "mystery": 1}
            )
        with self.assertRaises(ValueError):
            ArithmeticSkip.from_dict({"locator": "stem", "reason": "mystery-reason"})
        with self.assertRaises(ValueError):
            ArithmeticSkip.from_dict(
                {"locator": "stem", "reason": "free-variables", "extra": 1}
            )

    def test_check_is_pure_and_deterministic(self):
        question = make_question(["3+4*2", r"\frac{1}{2}"], text_answer("14"))
        snapshot = copy.deepcopy(question).to_dict()

        first = check_arithmetic(question)
        second = check_arithmetic(question)

        self.assertEqual(first, second)
        self.assertEqual(snapshot, question.to_dict())
        self.assertEqual(1, len(first.findings))
        self.assertEqual(1, len(first.skipped))



if __name__ == "__main__":
    unittest.main()
