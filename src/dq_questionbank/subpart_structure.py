"""Derive subquestions from top-level ``(1) (2) (n)`` numbering in imported stems.

Many imported composite questions arrive as one flat stem whose subparts are
numbered ``(1)``, ``(2)``, ``(3)`` ... This module infers those subparts and
maps them onto the existing canonical ``Question.subquestions`` field: every
inferred subquestion is a full question-shaped payload (``schema_version``,
``id``, ``type``, ``language``, ``stem``) that ``Question.from_dict`` accepts
directly and that carries no answer — the splitter never invents answers.

The inference is conservative and pure: the input stem is never mutated, and
whenever the numbering is ambiguous the stem is returned unchanged with a
machine-readable reason. A split happens only when the top-level numbering is

1. arabic — ``(1) (2) (3)`` — at the start of a text run/block or directly
   after a sentence boundary (``. ? ! ！ ？``) or a newline, so mid-sentence
   references such as ``(see (1) above)`` never split;
2. strictly increasing from ``(1)``;
3. covering the tail of the stem — after the first marker every text block
   must itself start a numbered part (zero-block tolerance), while non-text
   blocks (math, tables, images, ...) attach to the preceding part.

Roman numerals, letters, missing or out-of-order numbers, and unnumbered
prose inside the numbered tail each refuse the split with their own canonical
reason. Numbering inside math LaTeX is never considered, and leading
unnumbered context blocks stay with the parent stem. Part of #91.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import SCHEMA_VERSION, Content, ContentBlock

SUBPART_VERSION = "subpart/1"
SUBPART_QUESTION_TYPE = "short_answer"

REASON_EMPTY_STEM = "empty-stem"
REASON_NO_NUMBERING = "no-numbering"
REASON_INSUFFICIENT_NUMBERING = "insufficient-numbering"
REASON_NON_ARABIC = "non-arabic-numbering"
REASON_NON_MONOTONIC = "non-monotonic-numbering"
REASON_TRAILING = "trailing-unnumbered-content"

_INFERENCE_FIELDS = {"changed", "subquestions", "reasons"}

# A marker-like token is a parenthesized run of digits or ASCII letters. Any
# run that is not all digits (roman numerals, single letters, mixes such as
# ``3a``) counts as non-arabic numbering and refuses the split.
_MARKER_RE = re.compile(r"\(([0-9A-Za-z]+)\)")
_BOUNDARY_CHARS = ".?!！？\n"


@dataclass(frozen=True, slots=True)
class SubpartInference:
    """The outcome of subpart inference over one stem.

    ``subquestions`` holds full question-shaped payloads ready for
    ``Question.from_dict`` and is empty when the stem is unchanged;
    ``reasons`` carries exactly one canonical reason whenever the stem is
    left unchanged. Nothing here rewrites the input stem, and no answer is
    ever invented for an inferred subquestion.
    """

    changed: bool
    subquestions: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "subquestions": [dict(item) for item in self.subquestions],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubpartInference:
        unknown = sorted(set(data) - _INFERENCE_FIELDS)
        if unknown:
            raise ValueError(f"Unknown subpart-inference field(s): {', '.join(unknown)}.")
        raw_subquestions = data["subquestions"]
        if not isinstance(raw_subquestions, list):
            raise ValueError("Subpart-inference subquestions must be a list.")
        for item in raw_subquestions:
            if not isinstance(item, dict):
                raise ValueError("Subquestion payloads must be objects.")
        return cls(
            changed=bool(data["changed"]),
            subquestions=tuple(dict(item) for item in raw_subquestions),
            reasons=tuple(str(item) for item in data["reasons"]),
        )


@dataclass(frozen=True, slots=True)
class _Marker:
    """One numbering marker at a splittable position inside a text block."""

    block_index: int
    start: int
    end: int
    number: int | None

    @property
    def is_arabic(self) -> bool:
        return self.number is not None


def _is_at_boundary(text: str, start: int) -> bool:
    """Return True when a marker at ``start`` may begin a new subpart.

    Valid positions are the very start of the text and positions directly
    after a sentence boundary (``. ? ! ！ ？``) or a newline, optionally with
    whitespace in between. Mid-sentence parenthesized references therefore
    never qualify.
    """
    if start == 0:
        return True
    index = start - 1
    while index >= 0 and text[index].isspace():
        index -= 1
    return index >= 0 and text[index] in _BOUNDARY_CHARS


def _scan_markers(blocks: list[ContentBlock]) -> list[_Marker]:
    """Collect marker-like tokens at valid positions, in document order.

    Only text blocks are scanned; numbering inside math LaTeX or table cells
    is never considered.
    """
    markers: list[_Marker] = []
    for block_index, block in enumerate(blocks):
        if block.type != "text" or not block.text:
            continue
        for match in _MARKER_RE.finditer(block.text):
            if not _is_at_boundary(block.text, match.start()):
                continue
            token = match.group(1)
            markers.append(
                _Marker(
                    block_index=block_index,
                    start=match.start(),
                    end=match.end(),
                    number=int(token) if token.isdigit() else None,
                )
            )
    return markers


def _segment_blocks(markers: list[_Marker], blocks: list[ContentBlock]) -> list[list]:
    """Materialize the blocks of each numbered segment, in stem order.

    A segment starts at its marker (kept verbatim) and runs to the next
    marker. Non-text blocks between two marker-bearing blocks attach to the
    earlier segment, as does text that precedes a later marker inside its
    own block — it is glued to the previous part by the sentence boundary.
    """
    segments: list[list[ContentBlock]] = []
    for position, marker in enumerate(markers):
        block = blocks[marker.block_index]
        text = block.text or ""
        following = markers[position + 1] if position + 1 < len(markers) else None
        same_block = following is not None and following.block_index == marker.block_index
        cutoff = following.start if same_block else len(text)
        segment = [
            ContentBlock(
                type="text", text=text[marker.start:cutoff], language=block.language
            )
        ]
        last_index = following.block_index if following is not None else len(blocks)
        for index in range(marker.block_index + 1, last_index):
            segment.append(blocks[index])
        if following is not None and not same_block:
            next_block = blocks[following.block_index]
            next_text = next_block.text or ""
            leading = next_text[: following.start]
            if leading.strip():
                segment.append(
                    ContentBlock(type="text", text=leading, language=next_block.language)
                )
        segments.append(segment)
    return segments


def _subquestion_payload(sub_id: str, segment: list[ContentBlock]) -> dict[str, Any]:
    """Build one canonical subquestion payload for a numbered segment."""
    return {
        "schema_version": SCHEMA_VERSION,
        "id": sub_id,
        "type": SUBPART_QUESTION_TYPE,
        "language": "en",
        "stem": {"blocks": [block.to_dict() for block in segment]},
    }


def infer_subparts(stem: Content, base_id: str = "") -> SubpartInference:
    """Infer numbered subquestions from one imported stem (pure function).

    The stem is split only when arabic top-level markers ``(1) (2) ...``
    appear at valid positions, increase strictly from 1, and cover the tail
    of the stem with zero tolerance for unnumbered text blocks after the
    first marker. Each inferred subquestion gets the deterministic id
    ``{base_id}-p{n}`` (or ``p{n}`` when ``base_id`` is empty), the type
    ``short_answer``, the segment's blocks as its stem, and no answer.
    Everything else — empty stems, roman or letter numbering, missing or
    out-of-order numbers, trailing unnumbered prose — is returned unchanged
    with exactly one canonical reason.
    """
    blocks = list(stem.blocks)
    if not blocks:
        return SubpartInference(False, (), (REASON_EMPTY_STEM,))
    markers = _scan_markers(blocks)
    if not markers:
        return SubpartInference(False, (), (REASON_NO_NUMBERING,))
    if any(not marker.is_arabic for marker in markers):
        return SubpartInference(False, (), (REASON_NON_ARABIC,))
    if len(markers) < 2:
        return SubpartInference(False, (), (REASON_INSUFFICIENT_NUMBERING,))
    if [marker.number for marker in markers] != list(range(1, len(markers) + 1)):
        return SubpartInference(False, (), (REASON_NON_MONOTONIC,))
    marker_blocks = {marker.block_index for marker in markers}
    for index in range(markers[0].block_index, len(blocks)):
        if blocks[index].type == "text" and index not in marker_blocks:
            return SubpartInference(False, (), (REASON_TRAILING,))
    subquestions = tuple(
        _subquestion_payload(
            f"{base_id}-p{position}" if base_id else f"p{position}", segment
        )
        for position, segment in enumerate(_segment_blocks(markers, blocks), start=1)
    )
    return SubpartInference(changed=True, subquestions=subquestions, reasons=())
