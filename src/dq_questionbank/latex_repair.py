"""Deterministic, fail-closed repair rules for LaTeX formula sources.

This module hosts bounded quality rules that propose a repair for a LaTeX
source instead of silently rewriting it. The first rule repairs a formula
that is missing exactly one closing brace. Every other brace imbalance is
ambiguous by construction and is reported as a finding with the source left
untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

MISSING_CLOSING_BRACE_RULE = "latex-missing-closing-brace"

FINDING_MISSING_OPENING_BRACE = "latex-missing-opening-brace"
FINDING_MULTIPLE_BRACE_BREAKS = "latex-multiple-brace-breaks"
FINDING_AMBIGUOUS_CLOSING_BRACE = "latex-ambiguous-closing-brace"


@dataclass(frozen=True, slots=True)
class LatexRepairOutcome:
    """The result of one deterministic repair attempt.

    ``source`` always keeps the original input so it remains visible until a
    repair is explicitly accepted. ``latex`` is the proposed result and equals
    ``source`` unless a repair was applied. Exactly one of ``rule_id`` and
    ``finding_code`` is set for an unbalanced source.
    """

    source: str
    latex: str
    rule_id: str | None = None
    finding_code: str | None = None
    finding_message: str | None = None

    @property
    def repaired(self) -> bool:
        return self.rule_id is not None


def _brace_balance(latex: str) -> tuple[int, int]:
    """Return the final and minimum brace depth, ignoring escaped braces."""
    depth = 0
    minimum = 0
    index = 0
    length = len(latex)
    while index < length:
        char = latex[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < minimum:
                minimum = depth
        index += 1
    return depth, minimum


def _ends_with_lone_escape(latex: str) -> bool:
    """Report whether an appended brace would be swallowed by an escape."""
    count = 0
    index = len(latex) - 1
    while index >= 0 and latex[index] == "\\":
        count += 1
        index -= 1
    return count % 2 == 1


def repair_latex_braces(latex: str) -> LatexRepairOutcome:
    """Repair a LaTeX source that is missing exactly one closing brace.

    A repair is proposed only when a single closing brace restores balance
    deterministically: the running depth never drops below zero and ends at
    exactly one, and appending ``}`` cannot be swallowed by a trailing escape.
    A missing opening brace never has a unique insertion point, and two or
    more breaks are out of scope, so both are reported as findings with the
    source unchanged. Balanced sources are returned clean.
    """
    depth, minimum = _brace_balance(latex)
    if depth == 0 and minimum == 0:
        return LatexRepairOutcome(source=latex, latex=latex)
    if minimum < 0 and depth == -1:
        return LatexRepairOutcome(
            source=latex,
            latex=latex,
            finding_code=FINDING_MISSING_OPENING_BRACE,
            finding_message=(
                "A closing brace has no matching opening brace; the insertion "
                "point for '{' is ambiguous and needs manual review."
            ),
        )
    if minimum < 0 or depth >= 2 or depth < -1:
        return LatexRepairOutcome(
            source=latex,
            latex=latex,
            finding_code=FINDING_MULTIPLE_BRACE_BREAKS,
            finding_message=(
                "More than one brace break is present; deterministic single "
                "repair is not possible and the source needs manual review."
            ),
        )
    if _ends_with_lone_escape(latex):
        return LatexRepairOutcome(
            source=latex,
            latex=latex,
            finding_code=FINDING_AMBIGUOUS_CLOSING_BRACE,
            finding_message=(
                "The source ends with a lone escape; appending '}' would be "
                "escaped and the intended repair is ambiguous."
            ),
        )
    return LatexRepairOutcome(
        source=latex,
        latex=latex + "}",
        rule_id=MISSING_CLOSING_BRACE_RULE,
    )
