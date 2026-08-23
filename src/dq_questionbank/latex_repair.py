"""Deterministic, fail-closed repair rules for LaTeX formula sources.

This module hosts a small set of bounded quality rules that propose repairs
for a LaTeX source instead of silently rewriting it. Every outcome keeps the
original source visible so a reviewer can compare before accepting a change.

The current rule set:

- ``latex-missing-closing-brace``: append the single missing ``}`` when the
  repair is unambiguous.
- ``latex-bare-function-names``: prefix bare function names such as ``sin`` or
  ``cos`` with a backslash.
- ``latex-delimiter-spacing``: drop whitespace directly inside ``\\left(`` and
  ``\\right)`` style delimiters.
- ``latex-operator-spacing``: collapse two or more spaces around binary
  operators to a single space, outside ``\\text{...}`` regions.

Anything ambiguous — a missing opening brace, multiple brace breaks, a lone
trailing escape, or mismatched plain delimiters such as ``(x+1]`` — is
reported as a finding with the source left untouched. This is deliberately
not a general-purpose symbolic simplifier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MISSING_CLOSING_BRACE_RULE = "latex-missing-closing-brace"
BARE_FUNCTION_NAMES_RULE = "latex-bare-function-names"
DELIMITER_SPACING_RULE = "latex-delimiter-spacing"
OPERATOR_SPACING_RULE = "latex-operator-spacing"

FINDING_MISSING_OPENING_BRACE = "latex-missing-opening-brace"
FINDING_MULTIPLE_BRACE_BREAKS = "latex-multiple-brace-breaks"
FINDING_AMBIGUOUS_CLOSING_BRACE = "latex-ambiguous-closing-brace"
FINDING_MISMATCHED_DELIMITERS = "latex-mismatched-delimiters"


_FUNCTION_NAMES = (
    "arcsin",
    "arccos",
    "arctan",
    "sinh",
    "cosh",
    "tanh",
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "ln",
    "lg",
    "log",
    "exp",
    "det",
    "gcd",
    "lcm",
    "min",
    "max",
    "sup",
    "inf",
    "lim",
)

_BARE_FUNCTION_RE = re.compile(
    r"(?<![A-Za-z_\\])(" + "|".join(_FUNCTION_NAMES) + r")(?![A-Za-z])"
)
_LEFT_OPEN_RE = re.compile(r"(\\left\s*[\(\[\{])\s+")
_RIGHT_CLOSE_RE = re.compile(r"\s+(\\right\s*[\)\]\}])")
_OPERATORS = ("+", "-", "=", "<", ">")
_TEXT_REGION_RE = re.compile(r"\\(?:text|textrm)\{[^{}]*\}")
_MACRO_REGION_RE = re.compile(r"\\(?:mathrm|operatorname)\{[^{}]*\}")


@dataclass(frozen=True, slots=True)
class LatexRepairOutcome:
    """The result of one deterministic repair attempt.

    ``source`` always keeps the original input so it remains visible until a
    repair is explicitly accepted. ``latex`` is the proposed result and equals
    ``source`` unless a repair was applied. Exactly one of ``rule_id`` and
    ``finding_code`` is set for a source that needs attention.
    ``applied_rules`` lists every rule ID applied in order; for single-rule
    helpers it contains at most the one matching ``rule_id``.
    """

    source: str
    latex: str
    rule_id: str | None = None
    finding_code: str | None = None
    finding_message: str | None = None
    applied_rules: tuple[str, ...] = ()

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
        applied_rules=(MISSING_CLOSING_BRACE_RULE,),
    )


def _protected_spans(latex: str, include_macros: bool = False) -> list[tuple[int, int]]:
    """Return character spans that text rules must not touch.

    ``\\text{...}`` and ``\\textrm{...}`` hold prose whose spacing is
    intentional. With ``include_macros`` the protection extends to
    ``\\mathrm{...}`` and ``\\operatorname{...}`` argument regions. Nested
    braces are out of scope for these bounded rules.
    """
    patterns = [_TEXT_REGION_RE]
    if include_macros:
        patterns.append(_MACRO_REGION_RE)
    spans: list[tuple[int, int]] = []
    for pattern in patterns:
        spans.extend(match.span() for match in pattern.finditer(latex))
    spans.sort()
    return spans


def _apply_outside_spans(latex: str, spans: list[tuple[int, int]], rewrite) -> str:
    """Apply ``rewrite`` only to the parts of ``latex`` outside ``spans``."""
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(rewrite(latex[cursor:start]))
        pieces.append(latex[start:end])
        cursor = end
    pieces.append(rewrite(latex[cursor:]))
    return "".join(pieces)


def repair_bare_function_names(latex: str) -> LatexRepairOutcome:
    r"""Prefix bare function names with a backslash.

    ``sin x + cos x`` becomes ``\sin x + \cos x``. A name only counts when it
    stands alone: already-macro names such as ``\sin`` are skipped by the
    boundary check, longer words never match partially, and names inside
    ``\text{...}``, ``\mathrm{...}``, or ``\operatorname{...}`` regions are
    prose or intentional spellings and stay untouched.
    """

    def rewrite(segment: str) -> str:
        return _BARE_FUNCTION_RE.sub(lambda match: "\\" + match.group(0), segment)

    spans = _protected_spans(latex, include_macros=True)
    proposed = _apply_outside_spans(latex, spans, rewrite)
    if proposed == latex:
        return LatexRepairOutcome(source=latex, latex=latex)
    return LatexRepairOutcome(
        source=latex,
        latex=proposed,
        rule_id=BARE_FUNCTION_NAMES_RULE,
        applied_rules=(BARE_FUNCTION_NAMES_RULE,),
    )


def repair_delimiter_spacing(latex: str) -> LatexRepairOutcome:
    r"""Drop whitespace directly inside ``\left``/``\right`` delimiters.

    ``\left( x+1 \right)`` becomes ``\left(x+1\right)``. Whitespace directly
    after an opening ``\left(``-style delimiter or directly before a closing
    ``\right)``-style delimiter is semantically empty, so removing it is a
    clearly equivalent form. Spacing anywhere else is left alone.
    """
    proposed = _LEFT_OPEN_RE.sub(r"\1", latex)
    proposed = _RIGHT_CLOSE_RE.sub(r"\1", proposed)
    if proposed == latex:
        return LatexRepairOutcome(source=latex, latex=latex)
    return LatexRepairOutcome(
        source=latex,
        latex=proposed,
        rule_id=DELIMITER_SPACING_RULE,
        applied_rules=(DELIMITER_SPACING_RULE,),
    )


def repair_operator_spacing(latex: str) -> LatexRepairOutcome:
    r"""Collapse doubled spaces around binary operators outside prose.

    ``x  +  1`` becomes ``x + 1``: two or more spaces next to ``+ - = < >``
    collapse to exactly one space, which keeps unary/binary reading intact
    because single spaces and missing spaces are never introduced or removed.
    Spacing inside ``\text{...}`` and ``\textrm{...}`` is intentional prose
    layout and stays untouched, so ``\text{a  +  b}`` is preserved verbatim.
    """
    operator_class = "[" + re.escape("".join(_OPERATORS)) + "]"
    before_re = re.compile(r"[ ]{2,}(" + operator_class + ")")
    after_re = re.compile("(" + operator_class + ")[ ]{2,}")

    def rewrite(segment: str) -> str:
        segment = before_re.sub(r" \1", segment)
        return after_re.sub(r"\1 ", segment)

    spans = _protected_spans(latex)
    proposed = _apply_outside_spans(latex, spans, rewrite)
    if proposed == latex:
        return LatexRepairOutcome(source=latex, latex=latex)
    return LatexRepairOutcome(
        source=latex,
        latex=proposed,
        rule_id=OPERATOR_SPACING_RULE,
        applied_rules=(OPERATOR_SPACING_RULE,),
    )


def find_delimiter_mismatch(latex: str) -> str | None:
    """Report a message for mismatched plain ``()``/``[]`` delimiters.

    Escaped delimiters are skipped. A mismatch such as ``(x+1]`` has no
    single deterministic repair — the intended bracket cannot be guessed —
    so callers must surface it as a manual-review finding instead of
    rewriting the source. Braces are owned by the brace rules and are not
    checked here.
    """
    stack: list[str] = []
    index = 0
    length = len(latex)
    while index < length:
        char = latex[index]
        if char == "\\":
            index += 2
            continue
        if char in "([":
            stack.append(char)
        elif char in ")]":
            expected = "(" if char == ")" else "["
            if not stack or stack.pop() != expected:
                return (
                    "Plain delimiters are mismatched (for example '(' closed "
                    "by ']'); the intended form is ambiguous and needs "
                    "manual review."
                )
        index += 1
    if stack:
        return (
            "A plain opening delimiter has no closing partner; the intended "
            "form is ambiguous and needs manual review."
        )
    return None


def repair_latex_source(latex: str) -> LatexRepairOutcome:
    r"""Apply the deterministic rule set to one LaTeX source.

    Mismatched plain delimiters are checked first and fail closed as a
    finding. Otherwise the safe rules run in a fixed order — bare function
    names, ``\left``/``\right`` spacing, operator spacing, then the missing
    closing brace — each operating on the previous rule's proposal. The
    original ``source`` stays visible on the outcome, ``applied_rules``
    records every rule ID in order, and an already-clean source is returned
    unchanged with no rule applied.
    """
    mismatch = find_delimiter_mismatch(latex)
    if mismatch is not None:
        return LatexRepairOutcome(
            source=latex,
            latex=latex,
            finding_code=FINDING_MISMATCHED_DELIMITERS,
            finding_message=mismatch,
        )
    applied: list[str] = []
    current = latex
    for rule in (
        repair_bare_function_names,
        repair_delimiter_spacing,
        repair_operator_spacing,
    ):
        outcome = rule(current)
        if outcome.repaired:
            applied.append(outcome.rule_id or "")
            current = outcome.latex
    brace = repair_latex_braces(current)
    if brace.repaired:
        applied.append(brace.rule_id or "")
        current = brace.latex
    elif brace.finding_code is not None:
        return LatexRepairOutcome(
            source=latex,
            latex=latex,
            finding_code=brace.finding_code,
            finding_message=brace.finding_message,
        )
    if not applied:
        return LatexRepairOutcome(source=latex, latex=latex)
    return LatexRepairOutcome(
        source=latex,
        latex=current,
        rule_id=applied[0],
        applied_rules=tuple(rule_id for rule_id in applied if rule_id),
    )


