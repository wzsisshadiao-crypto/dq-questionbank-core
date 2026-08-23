"""Turn PDF chunks into transcription skeletons for humans to finish.

A chunk of raw PDF text is still far from a canonical question. This module
builds the bridge: a transcription skeleton with one slot per logical
field, each either pre-filled with what can be read deterministically
(stem lines, ``Answer key:`` rows, ``Worked solution:`` prose, ``|``-joined
table rows) or marked ``needs_human`` when the chunk never carried the
field at all. Humans fill the empty slots; the module never invents
content, and the finished skeleton maps one-to-one onto the canonical
question model. Part of #89.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import SCHEMA_VERSION
from .pdf_splitter import PdfChunk

PDF_SKELETON_VERSION = "pdf-skeleton/1"

STATUS_PREFILLED = "prefilled"
STATUS_NEEDS_HUMAN = "needs_human"

ANSWER_PREFIX = "Answer key:"
SOLUTION_PREFIX = "Worked solution:"
_TABLE_SEPARATOR = " | "

_SKELETON_FIELDS = {"version", "question_key", "slots"}
_SLOT_FIELDS = {"field", "status", "value", "page", "index"}


@dataclass(frozen=True, slots=True)
class SkeletonSlot:
    """One skeleton slot: a field, its fill status, and its source locator."""

    field: str
    status: str
    value: str | None
    page: int | None
    index: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "status": self.status,
            "value": self.value,
            "page": self.page,
            "index": self.index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkeletonSlot:
        unknown = sorted(set(data) - _SLOT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown skeleton-slot field(s): {', '.join(unknown)}.")
        return cls(
            field=str(data["field"]),
            status=str(data["status"]),
            value=data["value"],
            page=data["page"],
            index=data["index"],
        )


@dataclass(frozen=True, slots=True)
class TranscriptionSkeleton:
    """A per-chunk skeleton of slots humans finish into a question."""

    question_key: str
    slots: tuple[SkeletonSlot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PDF_SKELETON_VERSION,
            "question_key": self.question_key,
            "slots": [slot.to_dict() for slot in self.slots],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptionSkeleton:
        unknown = sorted(set(data) - _SKELETON_FIELDS)
        if unknown:
            raise ValueError(f"Unknown skeleton field(s): {', '.join(unknown)}.")
        if str(data.get("version", PDF_SKELETON_VERSION)) != PDF_SKELETON_VERSION:
            raise ValueError(f"Unsupported skeleton version: {data['version']!r}.")
        return cls(
            question_key=str(data["question_key"]),
            slots=tuple(SkeletonSlot.from_dict(item) for item in data["slots"]),
        )


def _classify(line_text: str) -> tuple[str, str]:
    """Map one chunk line to (field, value) using deterministic prefixes."""
    if line_text.startswith(ANSWER_PREFIX):
        return "answer", line_text[len(ANSWER_PREFIX) :].strip()
    if line_text.startswith(SOLUTION_PREFIX):
        return "solution", line_text[len(SOLUTION_PREFIX) :].strip()
    if _TABLE_SEPARATOR in line_text:
        return "stem", line_text
    return "stem", line_text


def build_skeleton(chunk: PdfChunk) -> TranscriptionSkeleton:
    """Build the transcription skeleton for one chunk (pure, deterministic).

    Every chunk line becomes exactly one pre-filled slot carrying its page
    and line locator; fields the chunk never mentions get one
    ``needs_human`` slot each so nothing is silently dropped. Values are
    never invented - answer/solution text is only the verbatim remainder
    after the deterministic prefix.
    """
    slots: list[SkeletonSlot] = []
    seen: set[str] = set()
    for line in chunk.lines:
        field, value = _classify(line.text)
        slots.append(
            SkeletonSlot(
                field=field,
                status=STATUS_PREFILLED,
                value=value,
                page=line.page,
                index=line.index,
            )
        )
        seen.add(field)
    for field in ("answer", "solution"):
        if field not in seen:
            slots.append(
                SkeletonSlot(
                    field=field,
                    status=STATUS_NEEDS_HUMAN,
                    value=None,
                    page=None,
                    index=None,
                )
            )
    return TranscriptionSkeleton(question_key=chunk.question_key, slots=tuple(slots))


def to_question_payload(skeleton: TranscriptionSkeleton) -> dict[str, Any]:
    """Project a skeleton onto the canonical question model (pure).

    Pre-filled stem slots become ordered text blocks; pre-filled answer and
    solution slots become the answer value and one solution text block.
    ``needs_human`` slots contribute nothing - the payload validates as a
    canonical question, but it is intentionally partial until a human has
    finished the skeleton.
    """
    stem_texts = [
        slot.value for slot in skeleton.slots
        if slot.field == "stem" and slot.status == STATUS_PREFILLED and slot.value
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": skeleton.question_key,
        "type": "short_answer",
        "language": "en",
        "stem": {"blocks": [{"type": "text", "text": text} for text in stem_texts]},
    }
    answer = next(
        (
            slot.value
            for slot in skeleton.slots
            if slot.field == "answer" and slot.status == STATUS_PREFILLED
        ),
        None,
    )
    if answer:
        payload["answer"] = {"kind": "text", "value": answer}
    solution = next(
        (
            slot.value
            for slot in skeleton.slots
            if slot.field == "solution" and slot.status == STATUS_PREFILLED
        ),
        None,
    )
    if solution:
        payload["solution"] = {"blocks": [{"type": "text", "text": solution}]}
    return payload

