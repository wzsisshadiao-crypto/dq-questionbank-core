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

    def test_malformed_frac(self) -> None:
        types = [f["type"] for f in detect_common_latex_faults(r"$\frac{a} b$")]
        self.assertIn("malformed-frac", types)

    def test_clean_source_has_no_faults(self) -> None:
        self.assertEqual(
            [], detect_common_latex_faults(r"$\frac{a}{b} + c^2 + d_i$")
        )


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
