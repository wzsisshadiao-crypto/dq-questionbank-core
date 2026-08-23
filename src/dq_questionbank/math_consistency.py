"""Conservative arithmetic consistency checks for LaTeX answers.

Verify simple numeric identities (bounded finite sums, direct arithmetic)
WITHOUT evaluating free variables; anything clever, ambiguous, or fishy is
skipped with a reason. Findings are reports, never rewrites. Part of #97.

The rules of conservatism, all of which must hold before a comparison runs:

- Candidates come only from the LaTeX of ``math`` blocks in the stem; a single
  surrounding pair of ``$...$``, ``\\(...\\)``, or ``\\[...\\]`` is stripped.
- An expression is evaluable only when it is fully numeric: digits, ``+``,
  ``-``, ``*``, ``/``, ``^``, parentheses, ``.``, and whitespace. Any ASCII
  letter means a free variable (``free-variables``); any other character,
  such as a macro or a brace, is ``unparseable-expression``.
- Ellipsis sums such as ``1 + 2 + 3 + \\cdots + 100`` are evaluated only when
  the listed terms form an exact arithmetic progression that lands on the
  final term and the full term count stays within :data:`MAX_SUM_TERMS`.
  ``\\sum`` notation names a bound variable and is never expanded.
- Evaluation uses a small hand-written recursive-descent parser over
  ``^ * / + -`` where ``^`` binds tightest and is right-associative; there is
  no ``eval`` and no new dependency.
- Division by zero and any intermediate or final magnitude above
  :data:`MAX_ABS_VALUE` skip with their own reasons.
- The answer side is consulted only for a ``text`` answer whose value is a
  plain number or a fully-numeric string; anything else is skipped with
  ``non-numeric-answer``.
- Each evaluable stem expression is compared with the answer independently,
  and a difference beyond a ``1e-9`` relative tolerance becomes one
  :class:`QualityFinding` citing both computed values, fingerprinted with
  the ``quality/1`` conventions so ``finding_state`` stays meaningful.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from .models import Answer, Question
from .quality_findings import RULESET_VERSION, QualityFinding, field_fingerprint

MATH_CONSISTENCY_VERSION = "math-consistency/1"
RULE_ARITHMETIC_MISMATCH = "arithmetic-mismatch"

# Documented cap for bounded finite sums; longer progressions are not evaluated.
MAX_SUM_TERMS = 1000
# Documented magnitude guard for every intermediate and final value.
MAX_ABS_VALUE = 10**12

_SKIP_FREE_VARIABLES = "free-variables"
_SKIP_NON_NUMERIC_ANSWER = "non-numeric-answer"
_SKIP_DIVISION_BY_ZERO = "division-by-zero"
_SKIP_SUM_TERMS_EXCEEDED = "sum-terms-exceeded"
_SKIP_MAGNITUDE_EXCEEDED = "magnitude-exceeded"
_SKIP_UNPARSEABLE_EXPRESSION = "unparseable-expression"
_SKIP_NO_NUMERIC_EXPRESSIONS = "no-numeric-expressions"

_SKIP_REASONS = frozenset(
    {
        _SKIP_FREE_VARIABLES,
        _SKIP_NON_NUMERIC_ANSWER,
        _SKIP_DIVISION_BY_ZERO,
        _SKIP_SUM_TERMS_EXCEEDED,
        _SKIP_MAGNITUDE_EXCEEDED,
        _SKIP_UNPARSEABLE_EXPRESSION,
        _SKIP_NO_NUMERIC_EXPRESSIONS,
    }
)
_SKIP_FIELDS = {"locator", "reason"}
_REPORT_FIELDS = {"findings", "skipped"}

_DIGITS = "0123456789"
_NUMERIC_GRAMMAR = frozenset(_DIGITS + "+-*/^(). \t")
_LETTER_RE = re.compile(r"[A-Za-z]")
_ELLIPSIS_MARKERS = ("\\cdots", "\\ldots", "\\dots", "...")
_DELIMITER_PAIRS = (("\\(", "\\)"), ("\\[", "\\]"), ("$", "$"))
_MAX_SAFE_EXPONENT = 40  # 2**40 already exceeds MAX_ABS_VALUE.
_MAX_TOKENS = 10_000
_MAX_PAREN_DEPTH = 64
_REL_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class ArithmeticSkip:
    """One conservative refusal to evaluate, with a stable reason.

    ``locator`` points at the input that was skipped, using the slash style
    ``stem/blocks/2`` for stem math blocks, ``stem`` for the whole stem, and
    ``answer`` for the answer side. ``reason`` is one of the closed
    snake-case vocabulary: ``free-variables``, ``non-numeric-answer``,
    ``division-by-zero``, ``sum-terms-exceeded``, ``magnitude-exceeded``,
    ``unparseable-expression``, ``no-numeric-expressions``.
    """

    locator: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"locator": self.locator, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArithmeticSkip:
        unknown = sorted(set(data) - _SKIP_FIELDS)
        if unknown:
            raise ValueError(f"Unknown arithmetic-skip field(s): {', '.join(unknown)}.")
        reason = str(data["reason"])
        if reason not in _SKIP_REASONS:
            raise ValueError(f"Unsupported arithmetic-skip reason: {reason!r}")
        return cls(locator=str(data["locator"]), reason=reason)


@dataclass(frozen=True, slots=True)
class ArithmeticCheckReport:
    """The outcome of one :func:`check_arithmetic` run.

    ``findings`` carries the mismatches as plain :class:`QualityFinding`
    objects (they serialize via their own ``to_dict``); ``skipped`` explains,
    with stable reasons, every input that conservatism refused to evaluate.
    """

    findings: tuple[QualityFinding, ...]
    skipped: tuple[ArithmeticSkip, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "skipped": [skip.to_dict() for skip in self.skipped],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArithmeticCheckReport:
        unknown = sorted(set(data) - _REPORT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown arithmetic-report field(s): {', '.join(unknown)}.")
        return cls(
            findings=tuple(QualityFinding.from_dict(item) for item in data["findings"]),
            skipped=tuple(ArithmeticSkip.from_dict(item) for item in data["skipped"]),
        )


class _SkipError(Exception):
    """Internal control-flow carrier for one conservative skip reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _guard(value: int | float) -> int | float:
    """Return ``value`` when it stays real and inside the magnitude cap."""
    if isinstance(value, complex):
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    if not abs(value) <= MAX_ABS_VALUE:
        raise _SkipError(_SKIP_MAGNITUDE_EXCEEDED)
    return value


def _safe_power(base: int | float, exponent: int | float) -> int | float:
    """Compute ``base ** exponent`` without unbounded big-integer work."""
    if (
        isinstance(base, int)
        and isinstance(exponent, int)
        and abs(base) >= 2
        and exponent >= _MAX_SAFE_EXPONENT
    ):
        raise _SkipError(_SKIP_MAGNITUDE_EXCEEDED)
    try:
        return base**exponent
    except OverflowError as error:
        raise _SkipError(_SKIP_MAGNITUDE_EXCEEDED) from error
    except ZeroDivisionError as error:
        raise _SkipError(_SKIP_DIVISION_BY_ZERO) from error


def _number(token: str) -> int | float:
    """Convert one numeric literal token, applying the magnitude guard."""
    try:
        value = float(token) if "." in token else int(token)
    except ValueError as error:
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION) from error
    return _guard(value)


def _tokenize(text: str) -> list[str]:
    """Split a grammar-clean expression into literals and operator tokens."""
    tokens: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char in " \t":
            index += 1
        elif char in "+-*/^()":
            tokens.append(char)
            index += 1
        elif char in _DIGITS or char == ".":
            start = index
            while index < length and (text[index] in _DIGITS or text[index] == "."):
                index += 1
            tokens.append(text[start:index])
        else:  # Unreachable after the grammar check; kept as a fail-closed net.
            raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    if len(tokens) > _MAX_TOKENS:
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    return tokens


class _Parser:
    """Recursive-descent parser for the fully-numeric expression grammar.

    Precedence, loosest to tightest: ``+ -``, then ``* /``, then unary
    ``+ -``, then right-associative ``^``. Integer literals stay integers so
    exact results such as ``2^3^2 == 512`` survive; every operation passes
    through the magnitude guard.
    """

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._position = 0
        self._depth = 0

    def parse(self) -> int | float:
        value = self._expr()
        if self._peek() is not None:
            raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
        return value

    def _peek(self) -> str | None:
        if self._position < len(self._tokens):
            return self._tokens[self._position]
        return None

    def _advance(self) -> str | None:
        token = self._peek()
        if token is not None:
            self._position += 1
        return token

    def _expr(self) -> int | float:
        value = self._term()
        while self._peek() in ("+", "-"):
            operator = self._advance()
            right = self._term()
            value = _guard(value + right if operator == "+" else value - right)
        return value

    def _term(self) -> int | float:
        value = self._unary()
        while self._peek() in ("*", "/"):
            operator = self._advance()
            right = self._unary()
            if operator == "*":
                value = _guard(value * right)
            else:
                if right == 0:
                    raise _SkipError(_SKIP_DIVISION_BY_ZERO)
                value = _guard(value / right)
        return value

    def _unary(self) -> int | float:
        if self._peek() in ("+", "-"):
            operator = self._advance()
            value = self._unary()
            if operator == "-":
                return _guard(-value)
            return value
        return self._power()

    def _power(self) -> int | float:
        base = self._primary()
        if self._peek() == "^":
            self._advance()
            exponent = self._unary()
            return _guard(_safe_power(base, exponent))
        return base

    def _primary(self) -> int | float:
        token = self._advance()
        if token is None or token in ("+", "-", "*", "/", "^", ")"):
            raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
        if token == "(":
            self._depth += 1
            if self._depth > _MAX_PAREN_DEPTH:
                raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
            value = self._expr()
            self._depth -= 1
            if self._advance() != ")":
                raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
            return value
        return _number(token)


def _strip_math_delimiters(latex: str) -> str:
    """Strip a single surrounding ``$``/``\\(...\\)``/``\\[...\\]`` pair."""
    text = latex.strip()
    for opener, closer in _DELIMITER_PAIRS:
        if (
            len(text) >= len(opener) + len(closer)
            and text.startswith(opener)
            and text.endswith(closer)
        ):
            return text[len(opener) : len(text) - len(closer)].strip()
    return text


def _find_ellipsis(text: str) -> tuple[int, int] | None:
    """Return the single ellipsis-marker span, or ``None`` when absent."""
    spans: list[tuple[int, int]] = []
    for marker in _ELLIPSIS_MARKERS:
        start = text.find(marker)
        while start != -1:
            spans.append((start, start + len(marker)))
            start = text.find(marker, start + len(marker))
    if len(spans) > 1:
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    if spans:
        return spans[0]
    return None


def _evaluate_plain(text: str) -> int | float:
    """Evaluate one delimiter-free, ellipsis-free numeric expression."""
    if _LETTER_RE.search(text):
        raise _SkipError(_SKIP_FREE_VARIABLES)
    if any(char not in _NUMERIC_GRAMMAR for char in text):
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    return _Parser(_tokenize(text)).parse()


def _evaluate_ellipsis(text: str, span: tuple[int, int]) -> int | float:
    r"""Evaluate an ``a + b + c + \cdots + z`` arithmetic progression.

    Only exact arithmetic progressions that land on the final term are
    evaluated, and only when the full term count stays within
    :data:`MAX_SUM_TERMS`; anything else is skipped as fishy. The sum is
    accumulated term by term so every intermediate stays inside the guard.
    """
    head = text[: span[0]].rstrip()
    tail = text[span[1] :].lstrip()
    if not head.endswith("+") or not tail.startswith("+"):
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    leading_terms = [segment.strip() for segment in head[:-1].split("+")]
    final_term = tail[1:].strip()
    if len(leading_terms) < 3 or "+" in final_term:
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    values = [_evaluate_plain(term) for term in leading_terms + [final_term]]
    leading = values[:-1]
    last = values[-1]
    steps = [leading[index + 1] - leading[index] for index in range(len(leading) - 1)]
    step = steps[0]
    if step == 0 or any(candidate != step for candidate in steps):
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    extra = (last - leading[-1]) / step
    extra_terms = round(extra)
    if extra_terms < 1 or abs(extra - extra_terms) > _REL_TOLERANCE:
        raise _SkipError(_SKIP_UNPARSEABLE_EXPRESSION)
    total_terms = len(leading) + extra_terms
    if total_terms > MAX_SUM_TERMS:
        raise _SkipError(_SKIP_SUM_TERMS_EXCEEDED)
    total = leading[0]
    value = leading[0]
    for _ in range(total_terms - 1):
        value = _guard(value + step)
        total = _guard(total + value)
    return total


def _evaluate_expression(latex: str) -> int | float:
    """Evaluate one stem math block under the conservative rules."""
    text = _strip_math_delimiters(latex)
    span = _find_ellipsis(text)
    if span is not None:
        return _evaluate_ellipsis(text, span)
    return _evaluate_plain(text)


def _evaluate_answer(answer: Answer | None) -> int | float:
    """Evaluate the answer side, or skip with ``non-numeric-answer``."""
    if answer is None or answer.kind != "text":
        raise _SkipError(_SKIP_NON_NUMERIC_ANSWER)
    value = answer.value
    if isinstance(value, bool):
        raise _SkipError(_SKIP_NON_NUMERIC_ANSWER)
    if isinstance(value, int):
        return _guard(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise _SkipError(_SKIP_NON_NUMERIC_ANSWER)
        return _guard(value)
    if isinstance(value, str):
        text = value.strip()
        if _LETTER_RE.search(text) or any(
            char not in _NUMERIC_GRAMMAR for char in text
        ):
            raise _SkipError(_SKIP_NON_NUMERIC_ANSWER)
        try:
            return _evaluate_plain(text)
        except _SkipError as skip:
            if skip.reason == _SKIP_UNPARSEABLE_EXPRESSION:
                raise _SkipError(_SKIP_NON_NUMERIC_ANSWER) from skip
            raise
    raise _SkipError(_SKIP_NON_NUMERIC_ANSWER)


def _differs(left: int | float, right: int | float) -> bool:
    """Return whether two values differ beyond the relative tolerance."""
    scale = max(1.0, abs(left), abs(right))
    return abs(left - right) > _REL_TOLERANCE * scale


def _build_finding(
    question: Question, index: int, stem_value: int | float, answer_value: int | float
) -> QualityFinding:
    """Build the mismatch finding, fingerprinting both sides it read."""
    block_path = f"stem.blocks[{index}]"
    return QualityFinding(
        question_id=question.id,
        target_field=block_path,
        rule_id=RULE_ARITHMETIC_MISMATCH,
        ruleset_version=RULESET_VERSION,
        input_fingerprints=(
            (block_path, field_fingerprint(question.stem.blocks[index].to_dict())),
            ("answer", field_fingerprint(question.answer.to_dict())),
        ),
        severity="warning",
        explanation=(
            f"Arithmetic mismatch: the stem block computes {stem_value} "
            f"but the answer says {answer_value}."
        ),
    )


def check_arithmetic(question: Question) -> ArithmeticCheckReport:
    """Run the conservative arithmetic checks over one question.

    The function is pure: it reads the question, evaluates what the rules of
    conservatism allow, and returns the findings and skips without touching
    the input. Each fully-numeric stem expression is compared with the
    numeric ``text`` answer independently; a mismatch becomes one finding,
    and every refusal to evaluate is reported as an :class:`ArithmeticSkip`.
    """
    findings: list[QualityFinding] = []
    skipped: list[ArithmeticSkip] = []
    blocks = [
        (index, block.latex)
        for index, block in enumerate(question.stem.blocks)
        if block.type == "math" and block.latex is not None
    ]
    if not blocks:
        return ArithmeticCheckReport(
            findings=(),
            skipped=(ArithmeticSkip(locator="stem", reason=_SKIP_NO_NUMERIC_EXPRESSIONS),),
        )
    evaluated: list[tuple[int, int | float]] = []
    for index, latex in blocks:
        try:
            value = _evaluate_expression(latex)
        except _SkipError as skip:
            reason = skip.reason
            skipped.append(ArithmeticSkip(locator=f"stem/blocks/{index}", reason=reason))
            continue
        evaluated.append((index, value))
    try:
        answer_value = _evaluate_answer(question.answer)
    except _SkipError as skip:
        skipped.append(ArithmeticSkip(locator="answer", reason=skip.reason))
    else:
        for index, value in evaluated:
            if _differs(value, answer_value):
                findings.append(_build_finding(question, index, value, answer_value))
    return ArithmeticCheckReport(findings=tuple(findings), skipped=tuple(skipped))




