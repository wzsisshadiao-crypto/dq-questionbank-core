"""LaTeX normalization engine with safe/review grading.

Mechanical LaTeX noise - double spaces, trailing blanks, padded inline
delimiters - wastes review time, and safe cleanups can apply automatically.
Risky rewrites (merging subscripts, inserting explicit multiplication) are
plausible but never certain, so they must never silently edit a formula.

Every rule carries a safety grade. ``autoFixable`` rules apply mechanically
inside :func:`normalize_latex`; ``reviewReason`` rules only ever contribute
a proposal (rule id, reason, current source, proposed text) and are
structurally unable to influence the normalized result - the engine's code
path for them never assigns to the output. The grade is the contract,
enforced by the engine, not by convention. Part of #94.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

LATEX_NORMALIZE_VERSION = "latex-normalize/1"

GRADE_AUTO_FIXABLE = "autoFixable"
GRADE_REVIEW_REASON = "reviewReason"

PROTECTED_REGION_RE = re.compile(
    r"\\(?:text|textrm|mathrm|operatorname)\{[^{}]*\}"
)
SPACE_RUN_RE = re.compile(r"  +")
TRAILING_SPACE_RE = re.compile(r" +$")
DOUBLE_SUBSCRIPT_RE = re.compile(r"_\{([^{}]*)\}_\{([^{}]*)\}")
DIGIT_LETTER_RE = re.compile(r"(\d+)([a-zA-Z])")

_RESULT_FIELDS = {"source", "result", "applied_rules", "proposals"}
_PROPOSAL_FIELDS = {"rule_id", "grade", "reason", "current", "proposed"}
_RULE_FIELDS = {"id", "grade", "explanation"}


@dataclass(frozen=True, slots=True)
class NormalizedLatex:
    """Outcome of one normalization run.

    ``source`` is always the untouched original; ``result`` equals it when
    nothing auto-applies; ``applied_rules`` lists the autoFixable rule ids
    that actually changed the text, in registry order; ``proposals`` holds
    one entry per matching reviewReason rule.
    """

    source: str
    result: str
    applied_rules: tuple[str, ...]
    proposals: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "result": self.result,
            "applied_rules": list(self.applied_rules),
            "proposals": [dict(item) for item in self.proposals],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedLatex:
        unknown = sorted(set(data) - _RESULT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown normalized-latex field(s): {', '.join(unknown)}.")
        proposals = []
        for item in data["proposals"]:
            if not isinstance(item, dict):
                raise ValueError("Normalization proposals must be objects.")
            unknown_proposal = sorted(set(item) - _PROPOSAL_FIELDS)
            if unknown_proposal:
                raise ValueError(
                    f"Unknown proposal field(s): {', '.join(unknown_proposal)}."
                )
            proposals.append(dict(item))
        return cls(
            source=str(data["source"]),
            result=str(data["result"]),
            applied_rules=tuple(str(item) for item in data["applied_rules"]),
            proposals=tuple(proposals),
        )


@dataclass(frozen=True, slots=True)
class NormalizationRule:
    """One graded rule: id, grade, explanation, match and apply callables.

    For ``reviewReason`` rules ``apply`` computes only the PROPOSED text;
    the engine never routes its return value into the result.
    """

    id: str
    grade: str
    explanation: str
    match: Callable[[str], bool]
    apply: Callable[[str], str]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "grade": self.grade, "explanation": self.explanation}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizationRule:
        unknown = sorted(set(data) - _RULE_FIELDS)
        if unknown:
            raise ValueError(f"Unknown rule field(s): {', '.join(unknown)}.")
        for rule in BUILT_IN_RULES:
            if rule.id == str(data["id"]):
                if rule.grade != str(data["grade"]):
                    raise ValueError(
                        f"Grade mismatch for rule {rule.id}: "
                        f"{data['grade']!r} != {rule.grade!r}."
                    )
                return rule
        raise ValueError(f"Unknown normalization rule id: {data['id']!r}.")


def _outside_protected(latex: str, rewrite: Callable[[str], str]) -> str:
    """Apply ``rewrite`` only outside \\text/\\mathrm style regions."""
    spans = [match.span() for match in PROTECTED_REGION_RE.finditer(latex)]
    if not spans:
        return rewrite(latex)
    parts: list[str] = []
    position = 0
    for start, end in spans:
        parts.append(rewrite(latex[position:start]))
        parts.append(latex[start:end])
        position = end
    parts.append(rewrite(latex[position:]))
    return "".join(parts)


def _collapse_space_runs(latex: str) -> str:
    return _outside_protected(latex, lambda text: SPACE_RUN_RE.sub(" ", text))


def _strip_trailing_space(latex: str) -> str:
    return _outside_protected(latex, lambda text: TRAILING_SPACE_RE.sub("", text))


def _normalize_inline_dollar_spacing(latex: str) -> str:
    def strip_padding(match: re.Match[str]) -> str:
        return f"${match.group(1).strip()}$"

    return re.sub(r"\$([^$\n]+)\$", strip_padding, latex)


def _merge_double_subscripts(latex: str) -> str:
    return DOUBLE_SUBSCRIPT_RE.sub(r"_{\1\2}", latex, count=1)


def _insert_explicit_multiplication(latex: str) -> str:
    return DIGIT_LETTER_RE.sub(r"\1 \\cdot \2", latex, count=1)


BUILT_IN_RULES: tuple[NormalizationRule, ...] = (
    NormalizationRule(
        id="collapse-space-runs",
        grade=GRADE_AUTO_FIXABLE,
        explanation="Collapse runs of two or more spaces to one outside text regions.",
        match=lambda latex: latex != _collapse_space_runs(latex),
        apply=_collapse_space_runs,
    ),
    NormalizationRule(
        id="strip-trailing-space",
        grade=GRADE_AUTO_FIXABLE,
        explanation="Remove trailing blank spaces outside text regions.",
        match=lambda latex: latex != _strip_trailing_space(latex),
        apply=_strip_trailing_space,
    ),
    NormalizationRule(
        id="normalize-inline-dollar-spacing",
        grade=GRADE_AUTO_FIXABLE,
        explanation="Drop padding spaces just inside single-dollar inline math.",
        match=lambda latex: latex != _normalize_inline_dollar_spacing(latex),
        apply=_normalize_inline_dollar_spacing,
    ),
    NormalizationRule(
        id="double-subscript-merge",
        grade=GRADE_REVIEW_REASON,
        explanation="Two consecutive subscript groups may be one merged subscript.",
        match=lambda latex: DOUBLE_SUBSCRIPT_RE.search(latex) is not None,
        apply=_merge_double_subscripts,
    ),
    NormalizationRule(
        id="implicit-multiplication-digit-letter",
        grade=GRADE_REVIEW_REASON,
        explanation="A digit glued to a letter may mean explicit multiplication.",
        match=lambda latex: DIGIT_LETTER_RE.search(latex) is not None,
        apply=_insert_explicit_multiplication,
    ),
)

_RULE_GRADES = (GRADE_AUTO_FIXABLE, GRADE_REVIEW_REASON)


def normalize_latex(
    source: str, rules: tuple[NormalizationRule, ...] = BUILT_IN_RULES
) -> NormalizedLatex:
    """Run graded normalization over one LaTeX source (pure, deterministic).

    autoFixable rules apply in registry order, each seeing the previous
    rule's output; a rule records its id only when it actually changes the
    text, which keeps every built-in cleanup idempotent. reviewReason rules
    are evaluated against the ORIGINAL source and contribute proposals
    only: their ``apply`` return value is never routed into ``result`` -
    a structural guarantee of the engine, not a convention. An unknown
    grade raises before anything runs.
    """
    for rule in rules:
        if rule.grade not in _RULE_GRADES:
            raise ValueError(f"Unknown normalization grade: {rule.grade!r}.")
    result = source
    applied: list[str] = []
    for rule in rules:
        if rule.grade != GRADE_AUTO_FIXABLE:
            continue
        if not rule.match(result):
            continue
        candidate = rule.apply(result)
        if candidate != result:
            applied.append(rule.id)
            result = candidate
    proposals = tuple(
        {
            "rule_id": rule.id,
            "grade": rule.grade,
            "reason": rule.explanation,
            "current": source,
            "proposed": rule.apply(source),
        }
        for rule in rules
        if rule.grade == GRADE_REVIEW_REASON and rule.match(source)
    )
    return NormalizedLatex(
        source=source, result=result, applied_rules=tuple(applied), proposals=proposals
    )

