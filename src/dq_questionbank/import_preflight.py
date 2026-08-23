"""Read-only duplicate preflight for import candidates.

Before review, an incoming candidate is fingerprinted against every
question already in a set and their document profiles are diffed, so a
re-import is caught before it can create a silent duplicate. The module
is strictly read-only: it never mutates its inputs, never persists, and
never writes; classification is conservative and deterministic.

Classification rules:

- an exact normalized fingerprint match is a ``duplicate`` (matched id
  recorded, reason ``fingerprint-match``);
- otherwise a matching document-profile signature — equal block/type/
  math/table/choice counts and a ``text_length`` within 5% relative
  difference — is a ``likely_duplicate`` with per-field diff evidence;
- anything else is ``unique``.

Fingerprints normalize text and LaTeX strings (lowercase, collapse
internal whitespace runs, strip) before the canonical-JSON SHA-256, in
the style of :func:`dq_questionbank.quality_findings.field_fingerprint`,
so case-only or whitespace-only differences still match.

Clean-room implementation from synthetic fixtures; part of issue #87.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .models import Question, QuestionSet

PREFLIGHT_VERSION = "preflight/1"

CLASS_DUPLICATE = "duplicate"
CLASS_LIKELY = "likely_duplicate"
CLASS_UNIQUE = "unique"
CLASSIFICATIONS = (CLASS_DUPLICATE, CLASS_LIKELY, CLASS_UNIQUE)

REASON_FINGERPRINT = "fingerprint-match"
REASON_PROFILE = "profile-signature-match"
REASON_NO_MATCH = "no-match"

# Two questions count as near-identical while their text lengths stay
# within this relative distance of each other.
TEXT_TOLERANCE = 0.05

_REPORT_FIELDS = {
    "classification",
    "candidate_fingerprint",
    "matched_question_id",
    "profile_diff",
    "reasons",
}

_WHITESPACE_RUN = re.compile(r"\s+")

# Identity and provenance fields never participate in a duplicate
# fingerprint: a re-import arrives under a new id with fresh metadata.
_FINGERPRINT_EXCLUDED_FIELDS = frozenset({"id", "schema_version", "source", "metadata"})


def _normalize_string(value: str) -> str:
    """Lowercase, collapse whitespace runs, and strip one string."""
    return _WHITESPACE_RUN.sub(" ", value).strip().lower()


def _normalize_payload(value: Any) -> Any:
    """Recursively normalize every string value in a plain payload."""
    if isinstance(value, str):
        return _normalize_string(value)
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_payload(item) for key, item in value.items()}
    return copy.deepcopy(value)


def question_fingerprint(question: Question) -> str:
    """Return the normalized-content fingerprint of one question.

    The fingerprint is the SHA-256 digest of the canonical JSON form of
    the question's ``to_dict`` payload after every text/latex string is
    normalized (lowercase, collapsed whitespace, stripped): sorted keys,
    compact separators, no ASCII escaping. Identity and provenance fields
    (``id``, ``schema_version``, ``source``, ``metadata``) are excluded
    so a re-import of the same content under a new id still matches;
    everything else — stem, choices, answer, solution, analysis, hints,
    tags, difficulty, taxonomy, subquestions, assets — is included.
    """
    payload = {
        key: value
        for key, value in question.to_dict().items()
        if key not in _FINGERPRINT_EXCLUDED_FIELDS
    }
    canonical = json.dumps(
        _normalize_payload(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def document_profile(question: Question) -> dict[str, Any]:
    """Return the deterministic document profile of one question.

    The profile counts the shape of the question — how many blocks of
    each type the stem carries, how much text it holds, how many choices
    exist — without keeping any of the wording.
    """
    blocks = question.stem.blocks if question.stem is not None else []
    block_types: dict[str, int] = {}
    text_length = 0
    math_count = 0
    table_count = 0
    for block in blocks:
        block_types[block.type] = block_types.get(block.type, 0) + 1
        if block.type == "text":
            text_length += len(block.text or "")
        elif block.type == "math":
            math_count += 1
        elif block.type == "table":
            table_count += 1
    return {
        "block_count": len(blocks),
        "block_types": dict(sorted(block_types.items())),
        "text_length": text_length,
        "math_count": math_count,
        "table_count": table_count,
        "choice_count": len(question.choices or []),
    }


def _within_text_tolerance(first: int, second: int) -> bool:
    if first == second:
        return True
    larger = max(first, second)
    if larger <= 0:
        return first == second
    return abs(first - second) / larger <= TEXT_TOLERANCE


def _same_signature(candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    return (
        candidate["block_count"] == existing["block_count"]
        and candidate["block_types"] == existing["block_types"]
        and candidate["math_count"] == existing["math_count"]
        and candidate["table_count"] == existing["table_count"]
        and candidate["choice_count"] == existing["choice_count"]
        and _within_text_tolerance(candidate["text_length"], existing["text_length"])
    )


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """One deterministic duplicate classification of an import candidate.

    ``profile_diff`` carries one evidence row per differing profile
    field (for example ``("text_length", "1024", "1030")``) when the
    classification is ``likely_duplicate``; it is empty otherwise. No
    timestamps, no provenance: the report is a pure function of its
    inputs.
    """

    classification: str
    candidate_fingerprint: str
    matched_question_id: str | None
    profile_diff: tuple[tuple[str, ...], ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "candidate_fingerprint": self.candidate_fingerprint,
            "matched_question_id": self.matched_question_id,
            "profile_diff": [list(row) for row in self.profile_diff],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PreflightReport:
        unknown = sorted(set(data) - _REPORT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown preflight-report field(s): {', '.join(unknown)}.")
        classification = str(data["classification"])
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"Unsupported classification: {classification!r}")
        matched = data.get("matched_question_id")
        return cls(
            classification=classification,
            candidate_fingerprint=str(data["candidate_fingerprint"]),
            matched_question_id=None if matched is None else str(matched),
            profile_diff=tuple(tuple(str(cell) for cell in row) for row in data["profile_diff"]),
            reasons=tuple(str(item) for item in data["reasons"]),
        )


def preflight(candidate: Question, existing: QuestionSet) -> PreflightReport:
    """Classify one candidate against an existing set (read-only, pure)."""
    candidate_fingerprint = question_fingerprint(candidate)
    candidate_profile = document_profile(candidate)

    for question in existing.questions:
        if question_fingerprint(question) == candidate_fingerprint:
            return PreflightReport(
                classification=CLASS_DUPLICATE,
                candidate_fingerprint=candidate_fingerprint,
                matched_question_id=question.id,
                profile_diff=(),
                reasons=(REASON_FINGERPRINT,),
            )

    for question in existing.questions:
        existing_profile = document_profile(question)
        if _same_signature(candidate_profile, existing_profile):
            diff = (
                (
                    "text_length",
                    str(candidate_profile["text_length"]),
                    str(existing_profile["text_length"]),
                ),
            )
            return PreflightReport(
                classification=CLASS_LIKELY,
                candidate_fingerprint=candidate_fingerprint,
                matched_question_id=question.id,
                profile_diff=diff,
                reasons=(REASON_PROFILE,),
            )

    return PreflightReport(
        classification=CLASS_UNIQUE,
        candidate_fingerprint=candidate_fingerprint,
        matched_question_id=None,
        profile_diff=(),
        reasons=(REASON_NO_MATCH,),
    )

