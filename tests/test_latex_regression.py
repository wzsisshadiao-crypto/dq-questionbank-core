from __future__ import annotations

import unittest

from dq_questionbank.latex_regression import (
    DEFAULT_CASES_PATH,
    detect_common_latex_faults,
    load_cases,
    run_case,
    run_regression_cases,
)


class DetectCommonLatexFaultsTests(unittest.TestCase):
    def test_double_superscript(self) -> None:
        types = [f["type"] for f in detect_common_latex_faults("$x^2^3$")]
        self.assertIn("double-superscript", types)

    def test_double_subscript(self) -> None:
        types = [f["type"] for f in detect_common_latex_faults("$a_1_2$")]
        self.assertIn("double-subscript", types)

    def test_single_token_frac_arguments_are_valid(self) -> None:
        for source in (
            r"$\frac a b$",
            r"$\frac{a} b$",
            r"$\frac 1 2$",
            r"$\frac\alpha2$",
            r"$\frac{{a+b}}{\sqrt{x}}$",
        ):
            with self.subTest(source=source):
                self.assertEqual([], detect_common_latex_faults(source))

    def test_missing_or_unbalanced_frac_argument_is_detected(self) -> None:
        for source in (r"$\frac{a}$", r"$\frac 1$", r"$\frac{a}{b$", r"$\frac$"):
            with self.subTest(source=source):
                types = [f["type"] for f in detect_common_latex_faults(source)]
                self.assertIn("malformed-frac", types)

    def test_fraction_before_closing_math_delimiter_is_incomplete(self) -> None:
        types = [f["type"] for f in detect_common_latex_faults(r"\(\frac a\)")]
        self.assertIn("malformed-frac", types)

    def test_clean_source_has_no_faults(self) -> None:
        self.assertEqual(
            [], detect_common_latex_faults(r"$\frac{a}{b} + c^2 + d_i$")
        )

    def test_commands_and_scripts_in_tex_comments_are_ignored(self) -> None:
        for source in (
            "% " + r"\frac{a}" + "\n$x+1$",
            r"$x$ % synthetic x^2^3 and a_1_2",
            r"\\% synthetic \frac{a}" + "\n$x$",
        ):
            with self.subTest(source=source):
                self.assertEqual([], detect_common_latex_faults(source))

    def test_comments_do_not_supply_fraction_arguments_or_closing_braces(self) -> None:
        for source in (
            r"\(\frac a% synthetic denominator b" + "\n" + r"\)",
            r"$\frac{a}{b% synthetic closer }" + "\n$",
            r"$\frac{a}% synthetic denominator b",
        ):
            with self.subTest(source=source):
                self.assertIn(
                    "malformed-frac", [f["type"] for f in detect_common_latex_faults(source)]
                )

    def test_fraction_arguments_can_follow_comments(self) -> None:
        for newline in ("\n", "\r\n", "\r"):
            for source in (
                r"\(\frac a% synthetic note" + newline + r"b\)",
                r"\(\frac% synthetic note" + newline + r"{a}% synthetic note" + newline + r"{b}\)",
            ):
                with self.subTest(newline=newline, source=source):
                    self.assertEqual([], detect_common_latex_faults(source))

    def test_escaped_percent_keeps_following_source_visible(self) -> None:
        self.assertEqual([], detect_common_latex_faults(r"$\frac\%2$"))
        self.assertIn(
            "malformed-frac",
            [f["type"] for f in detect_common_latex_faults(r"$\% \frac{a}$")],
        )

    def test_comments_do_not_join_control_word_fragments(self) -> None:
        source = r"$\frac\al% synthetic note" + "\npha$"
        self.assertEqual([], detect_common_latex_faults(source))
        source = r"$\fr% synthetic note" + "\nac{a}$"
        self.assertEqual([], detect_common_latex_faults(source))

    def test_active_script_faults_across_comments_are_still_detected(self) -> None:
        for source, expected in (
            ("$x^% synthetic note\n2^3$", "double-superscript"),
            ("$a_1% synthetic note\n_2$", "double-subscript"),
        ):
            with self.subTest(source=source):
                self.assertIn(expected, [f["type"] for f in detect_common_latex_faults(source)])


class BuiltinCasesTests(unittest.TestCase):
    def test_all_builtin_cases_pass(self) -> None:
        report = run_regression_cases(load_cases())
        self.assertTrue(report["ok"], report["results"])
        self.assertGreaterEqual(report["case_count"], 9)

    def test_builtin_file_exists_and_is_pinned(self) -> None:
        self.assertTrue(DEFAULT_CASES_PATH.is_file())

    def test_trinity_case_detect_count_repair(self) -> None:
        result = run_case({
            "name": "trinity-demo",
            "text": r"$a=1$，$\quad b=2$",
            "transform": "restore_degraded_relation_pairs",
            "expect_issue_types": [],
            "expect_fix_count": 1,
            "expect_equals": "$a=1$，$b=2$",
        })
        self.assertTrue(result["ok"], result["errors"])

    def test_wrong_count_fails_by_name(self) -> None:
        result = run_case({
            "name": "count-mismatch-demo",
            "text": r"$a=1$，$\quad b=2$",
            "transform": "restore_degraded_relation_pairs",
            "expect_fix_count": 2,
        })
        self.assertFalse(result["ok"])
        self.assertTrue(any("fix count" in e for e in result["errors"]))

    def test_regression_fires_on_behaviour_change(self) -> None:
        # If the repair ever merges coordinate pairs, this pinned case fails.
        result = run_case({
            "name": "coordinates-guard",
            "text": r"points $(x,y)$，$\quad (u,v)$",
            "transform": "restore_degraded_relation_pairs",
            "expect_fix_count": 0,
            "expect_equals": r"points $(x,y)$，$\quad (u,v)$",
        })
        self.assertTrue(result["ok"], result["errors"])

    def test_unknown_transform_is_reported_not_raised(self) -> None:
        result = run_case({"name": "bad", "text": "$x$", "transform": "nope"})
        self.assertFalse(result["ok"])
        self.assertTrue(any("unknown transform" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
