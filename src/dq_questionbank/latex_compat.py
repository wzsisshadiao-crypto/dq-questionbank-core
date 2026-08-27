"""LaTeX compatibility repairs for PDF-transcribed math.

Two degradation shapes show up whenever math is transcribed from rendered
PDF evidence, and both have precise, reviewable fixes:

1. **Degraded relation pairs.** A source that was one formula with a
   typographic comma plus ``\\quad`` spacing — ``$u=\\xi+\\eta$`` followed by
   ``$\\quad v=\\xi-\\eta$`` — carries a stray ``\\quad`` at the start of the
   second span. :func:`restore_degraded_relation_pairs` removes that stray
   spacing only when **both** sides are relation expressions (operands
   around a relation operator). Independent formulas, coordinates,
   intervals, and function arguments are left untouched, and three-column
   sources degrade into two adjacent footprints which the scan rebuilds
   pair by pair.

2. **Bare differentials inside integrals.** ``$\\int_0^1 x\\,dx$`` should
   render its differential upright: ``\\mathrm{d}x``.
   :func:`normalize_integral_differentials` rewrites bare ``dx``/``d\\theta``
   only inside inline-math spans that contain an integral command, and
   never touches an already-upright ``\\mathrm{d}``.

Both functions are pure string-to-string maps that take an optional
``stats`` dictionary and count their fixes under stable keys, so callers
can report how much was repaired.
"""

from __future__ import annotations

import re

RELATION_OPERATOR_RE = re.compile(
    r"[=<>≤≥≠≈∼∈∉⊂⊆⊃⊇]"
    r"|\\(?:approx|cong|equiv|ge|geq|geqslant|gt|in|le|leq|"
    r"leqslant|lt|ne|neq|notin|propto|sim|simeq|subset|subseteq|"
    r"supset|supseteq|to|mapsto|rightarrow)(?![A-Za-z])"
)

DEGRADED_RELATION_PAIR_RE = re.compile(
    r"(?<!\$)\$(?!\$)(?P<left>[^$\r\n]+)\$(?!\$)"
    r"，"
    r"\$(?!\$)\\(?P<spacing>quad|qquad)(?![A-Za-z])"
    r"(?P<right>[ \t]*[^$\r\n]+)\$(?!\$)"
)

INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(?P<body>[^$\r\n]+)\$(?!\$)")

INTEGRAL_COMMAND_RE = re.compile(r"\\(?:int|iint|iiint|oint|oiint|oiiint)(?![A-Za-z])")

BARE_DIFFERENTIAL_RE = re.compile(
    r"(?<![A-Za-z\\])d(?P<gap>[ \t]*)(?P<variable>"
    r"[A-Za-z](?![A-Za-z])|"
    r"\\(?:alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|"
    r"vartheta|iota|kappa|lambda|mu|nu|xi|pi|varpi|rho|varrho|sigma|"
    r"varsigma|tau|upsilon|phi|varphi|chi|psi|omega)(?![A-Za-z]))"
)

DEGRADED_PAIR_STATS_KEY = "degraded_relation_pair_fixes"
DIFFERENTIAL_STATS_KEY = "integral_differential_fixes"


def is_relation_expression(fragment: str) -> bool:
    """Return True only when a math fragment has operands around a relation.

    ``u=\\xi+\\eta`` qualifies; ``(x,y)``, ``[a,b]``, and ``f(x,y)`` do not
    (their ``=``/``<``-like characters, if any, lack operands on both
    sides), which is what keeps independent spans from being merged.
    """
    value = str(fragment or "")
    for match in RELATION_OPERATOR_RE.finditer(value):
        if value[: match.start()].strip() and value[match.end():].strip():
            return True
    return False


def restore_degraded_relation_pairs(
    text: str, stats: dict | None = None
) -> str:
    """Restore the exact ``$A$，$\\quad B$`` PDF degradation footprint.

    The stray ``\\quad``/``\\qquad`` is dropped from the head of the second
    span only when both spans are relation expressions. The replacement is
    re-scanned, so a three-column source (``$A$，$\\quad B$，$\\qquad C$``)
    converges pair by pair. Fixes are counted under
    :data:`DEGRADED_PAIR_STATS_KEY`.
    """
    value = str(text or "")
    fixed = 0

    def replace(match: re.Match) -> str:
        nonlocal fixed
        left = match.group("left").strip()
        right = match.group("right").strip()
        if not (is_relation_expression(left) and is_relation_expression(right)):
            return match.group(0)
        fixed += 1
        return f"${left}$，${right}$"

    while True:
        normalized = DEGRADED_RELATION_PAIR_RE.sub(replace, value)
        if normalized == value:
            break
        value = normalized
    if fixed and stats is not None:
        stats[DEGRADED_PAIR_STATS_KEY] = (
            stats.get(DEGRADED_PAIR_STATS_KEY, 0) + fixed
        )
    return value


def normalize_integral_differentials(
    text: str, stats: dict | None = None
) -> str:
    """Use upright ``\\mathrm{d}`` only for bare differentials inside integrals.

    Math spans without an integral command are returned unchanged, and a
    differential already preceded by ``\\mathrm``/``\\mathrm{`` is left
    alone. Fixes are counted under :data:`DIFFERENTIAL_STATS_KEY`.
    """
    fixed = 0

    def normalize_math(match: re.Match) -> str:
        nonlocal fixed
        body = match.group("body")
        if not INTEGRAL_COMMAND_RE.search(body):
            return match.group(0)

        def replace_differential(diff_match: re.Match) -> str:
            nonlocal fixed
            prefix = body[: diff_match.start()]
            if re.search(r"\\mathrm\s*(?:\{\s*)?$", prefix):
                return diff_match.group(0)
            fixed += 1
            return (
                r"\mathrm d"
                + diff_match.group("gap")
                + diff_match.group("variable")
            )

        return f"${BARE_DIFFERENTIAL_RE.sub(replace_differential, body)}$"

    value = INLINE_MATH_RE.sub(normalize_math, str(text or ""))
    if fixed and stats is not None:
        stats[DIFFERENTIAL_STATS_KEY] = (
            stats.get(DIFFERENTIAL_STATS_KEY, 0) + fixed
        )
    return value


__all__ = [
    "BARE_DIFFERENTIAL_RE",
    "DEGRADED_PAIR_STATS_KEY",
    "DEGRADED_RELATION_PAIR_RE",
    "DIFFERENTIAL_STATS_KEY",
    "INLINE_MATH_RE",
    "INTEGRAL_COMMAND_RE",
    "RELATION_OPERATOR_RE",
    "is_relation_expression",
    "normalize_integral_differentials",
    "restore_degraded_relation_pairs",
]

