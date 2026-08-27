"""LaTeX regression lock: pinned cases for rule changes.

When a correction, normalization, or repair rule changes, the question is
never "does the suite still pass" but "does this exact input still produce
this exact output". This module pins those pairs.

Each case is the **trinity in one assertion**:

- **detect** - ``expect_issue_types`` pins which faults the recognizer
  finds in the raw text (double superscript/subscript, malformed ``\\frac``,
  degraded relation pairs);
- **count** - ``expect_fix_count`` pins how many fixes the repair applies
  (via the shared stats dictionary contract of :mod:`.latex_compat`);
- **repair** - ``expect_equals`` / ``expect_contains`` /
  ``expect_not_contains`` pin the repaired text itself.

Workflow: before changing any LaTeX rule, add (or confirm) a case that
documents the current behaviour, run
``python -m dq_questionbank.latex_regression`` (all cases must PASS), make
the change, and run again. Behaviour changes surface as named failures -
including intentional ones, which is exactly what a reviewer wants to see.

The checked-in cases (:data:`DEFAULT_CASES_PATH`) are the project's
collective memory of hard-won edge cases: coordinates that must not merge,
three-column relation chains that must, upright differentials only inside
integrals, and classic lint faults.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .latex_compat import (
    DEGRADED_PAIR_STATS_KEY,
    DIFFERENTIAL_STATS_KEY,
    normalize_integral_differentials,
    restore_degraded_relation_pairs,
)

CASE_SCHEMA = "latex-regression-case/v1"

#: Recognized fault types (the "detect" leg of the trinity).
FAULT_DOUBLE_SUPERSCRIPT = "double-superscript"
FAULT_DOUBLE_SUBSCRIPT = "double-subscript"
FAULT_MALFORMED_FRAC = "malformed-frac"

_DOUBLE_SUP_RE = re.compile(r"\^(?:\{[^{}]*\}|\S)(?:\s*\^(?:\{[^{}]*\}|\S))")
_DOUBLE_SUB_RE = re.compile(r"_(?:\{[^{}]*\}|\S)(?:\s*_(?:\{[^{}]*\}|\S))")
_MALFORMED_FRAC_RE = re.compile(r"\\frac\s*\{[^{}]*\}\s*(?![{\\A-Za-z])")

DEFAULT_CASES_PATH = (
    Path(__file__).resolve().parent / "data" / "latex_regression_cases.json"
)

_TRANSFORMS = {
    "restore_degraded_relation_pairs": restore_degraded_relation_pairs,
    "normalize_integral_differentials": normalize_integral_differentials,
}


def detect_common_latex_faults(text: str) -> list[dict]:
    """Detect structural LaTeX faults that no repair should ever introduce."""
    value = str(text or "")
    faults: list[dict] = []
    if _DOUBLE_SUP_RE.search(value):
        faults.append({"type": FAULT_DOUBLE_SUPERSCRIPT})
    if _DOUBLE_SUB_RE.search(value):
        faults.append({"type": FAULT_DOUBLE_SUBSCRIPT})
    if _MALFORMED_FRAC_RE.search(value):
        faults.append({"type": FAULT_MALFORMED_FRAC})
    return faults


def _stats_key_for(transform: str) -> str:
    if transform == "restore_degraded_relation_pairs":
        return DEGRADED_PAIR_STATS_KEY
    if transform == "normalize_integral_differentials":
        return DIFFERENTIAL_STATS_KEY
    return ""


def run_case(case: dict) -> dict:
    """Execute one trinity case; returns a result dict (never raises)."""
    name = str(case.get("name") or "<unnamed>")
    errors: list[str] = []
    text = str(case.get("text") or "")

    issues = [fault["type"] for fault in detect_common_latex_faults(text)]
    expected_issues = list(case.get("expect_issue_types") or [])
    if expected_issues or "expect_issue_types" in case:
        if sorted(issues) != sorted(expected_issues):
            errors.append(
                f"detected issues {sorted(issues)} != expected "
                f"{sorted(expected_issues)}"
            )

    transform_name = str(case.get("transform") or "")
    result_text = text
    fix_count = None
    if transform_name:
        transform = _TRANSFORMS.get(transform_name)
        if transform is None:
            errors.append(f"unknown transform {transform_name!r}")
        else:
            stats: dict = {}
            result_text = transform(text, stats)
            key = _stats_key_for(transform_name)
            fix_count = stats.get(key, 0)

    expected_count = case.get("expect_fix_count")
    if expected_count is not None:
        if fix_count != expected_count:
            errors.append(
                f"fix count {fix_count} != expected {expected_count}"
            )
        elif fix_count is None:
            errors.append("expect_fix_count set but no transform ran")

    if "expect_equals" in case and result_text != case["expect_equals"]:
        errors.append(f"result {result_text!r} != expected equality")
    for fragment in case.get("expect_contains") or []:
        if fragment not in result_text:
            errors.append(f"result missing expected fragment {fragment!r}")
    for fragment in case.get("expect_not_contains") or []:
        if fragment in result_text:
            errors.append(f"result must not contain {fragment!r}")

    residual = [fault["type"] for fault in detect_common_latex_faults(result_text)]
    if case.get("expect_no_faults_after") and residual:
        errors.append(f"faults remain after repair: {sorted(residual)}")

    return {"name": name, "ok": not errors, "errors": errors}


def load_cases(path: str | Path = DEFAULT_CASES_PATH) -> list[dict]:
    """Load trinity cases from a JSON file (must be a list of case objects)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"regression cases must be a JSON list: {path}")
    return data


#: Stable alias so the public API reads uniformly.
load_regression_cases = load_cases


def run_regression_cases(cases: list[dict]) -> dict:
    """Run every case; the report is data, exceptions stay with the caller."""
    results = [run_case(case) for case in cases]
    failed = [result for result in results if not result["ok"]]
    return {
        "schema": CASE_SCHEMA,
        "case_count": len(results),
        "failed_count": len(failed),
        "ok": not failed,
        "results": results,
    }


def main() -> int:
    report = run_regression_cases(load_cases())
    print(f"cases={report['case_count']} failed={report['failed_count']}")
    for result in report["results"]:
        print(f"{'PASS' if result['ok'] else 'FAIL'} {result['name']}")
        for error in result["errors"]:
            print(f"  - {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CASE_SCHEMA",
    "DEFAULT_CASES_PATH",
    "FAULT_DOUBLE_SUBSCRIPT",
    "FAULT_DOUBLE_SUPERSCRIPT",
    "FAULT_MALFORMED_FRAC",
    "detect_common_latex_faults",
    "load_cases",
    "load_regression_cases",
    "run_case",
    "run_regression_cases",
]

