"""Question-ID expansion for the Word publishing macro insert box.

The Word publishing macro lets a typist enter a short reference such as ``6``
or ``DLLG_2025_6`` instead of the full ``KY_SX_SF_DLLG_2025_6`` identifier.
The macro keeps the last used subject, school, and year in Word ``SaveSetting``
memory and expands the short form against that memory before asking the
server for the question.

This module is the algorithmic reference for that expansion. It is a pure
function over strings plus an explicit memory object, so the same tests that
pin the Python behaviour can be transcribed to VBA when the macro changes:

- whitespace and underscores are interchangeable while typing
  (``KY SX SF SEU 2025 4`` equals ``KY_SX_SF_SEU_2025_4``),
- a full identifier seeds the memory and is returned unchanged,
- short forms borrow the missing subject, school, or year from the memory,
- comma-separated batches expand every element (all-or-nothing),
- legacy range specifications pass through untouched, and
- ambiguous or malformed input returns ``None`` so the caller can hand the
  raw text to the server instead of guessing.
"""

from __future__ import annotations

import re

RESERVED_TOKENS = ("KY", "SX", "SF", "GD")
SUBJECT_TOKENS = ("SF", "GD")
FULL_ID_PREFIX = "KY_SX_"

_SEPARATOR_RUN_RE = re.compile(r"[\s_]+")


class WordMacroIdMemory:
    """Last used subject, school, and year (the ``SaveSetting`` equivalent)."""

    def __init__(
        self, subject: str = "SF", school: str = "", year: str = ""
    ) -> None:
        self.subject = subject
        self.school = school
        self.year = year

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"WordMacroIdMemory(subject={self.subject!r}, "
            f"school={self.school!r}, year={self.year!r})"
        )


def normalize_spec_separators(spec: str) -> str:
    """Collapse whitespace/underscore runs into single underscores.

    Underscores hugging a comma are removed so batch input such as
    ``7, 8, 9`` normalizes to ``7,8,9`` before expansion.
    """
    value = _SEPARATOR_RUN_RE.sub("_", str(spec or "").strip())
    return value.replace(",_", ",").replace("_,", ",")


def is_year_token(token: str) -> bool:
    """Return True for four-digit years in the 19xx/20xx range."""
    return len(token) == 4 and token.isdigit() and token[:2] in ("19", "20")


def expand_question_spec(spec: str, memory: WordMacroIdMemory) -> str | None:
    """Expand a typed reference to a full identifier, or return None.

    The memory is updated whenever a full identifier or a short form pins
    down the subject, school, or year. ``None`` means "not recognizable";
    callers should forward the raw input to the server in that case.
    """
    value = normalize_spec_separators(spec)
    if not value:
        return None
    if value.upper().startswith(FULL_ID_PREFIX):
        rest = value[len(FULL_ID_PREFIX):].split("_")
        if (
            len(rest) == 4
            and rest[0].upper() in SUBJECT_TOKENS
            and rest[1].upper() not in RESERVED_TOKENS
            and rest[1].isalpha()
            and is_year_token(rest[2])
            and rest[3].isdigit()
        ):
            memory.subject = rest[0].upper()
            memory.school = rest[1].upper()
            memory.year = rest[2]
            return value
        return None  # full-ID shape with bad segments: let the server decide
    if "," in value:
        expanded = []
        for part in value.split(","):
            result = expand_question_spec(part, memory)
            if result is None:
                return None
            expanded.append(result)
        return ",".join(expanded)
    if "-" in value:
        return value  # legacy range semantics: untouched
    segments = [segment for segment in value.split("_") if segment]
    if len(segments) > 4:
        return None
    number = segments[-1]
    if not (number.isdigit() and len(number) <= 3):
        return None
    year = ""
    head = segments[:-1]
    if head and is_year_token(head[-1]):
        year = head[-1]
        head = head[:-1]
    if len(head) > 2:
        return None
    subject = school = ""
    if len(head) == 2:
        if head[0].upper() not in SUBJECT_TOKENS:
            return None
        if head[1].upper() in RESERVED_TOKENS or not head[1].isalpha():
            return None
        subject, school = head[0].upper(), head[1].upper()
    elif len(head) == 1:
        token = head[0].upper()
        if token in SUBJECT_TOKENS:
            subject = token
        elif token in RESERVED_TOKENS or not head[0].isalpha():
            return None
        else:
            school = token
    subject = subject or memory.subject
    school = school or memory.school
    year = year or memory.year
    if not (subject and school and year):
        return None
    memory.subject = subject
    memory.school = school
    memory.year = year
    return f"{FULL_ID_PREFIX}{subject}_{school}_{year}_{number}"


__all__ = [
    "FULL_ID_PREFIX",
    "RESERVED_TOKENS",
    "SUBJECT_TOKENS",
    "WordMacroIdMemory",
    "expand_question_spec",
    "is_year_token",
    "normalize_spec_separators",
]
