"""Conservatively map images extracted during import onto questions using
paragraph-range evidence; never guess — uncertain placements return an
explicit unknown with a human-readable reason. Part of #90.

Import pipelines can usually locate an image on the page but cannot
always prove which question owns it. This module is the pure inference
half of that decision: given one inclusive paragraph range per extracted
image and one ordered, non-overlapping paragraph range per question, it
either proves containment or refuses to guess.

Rules, evaluated per image (first match wins):

1. ``invalid-range`` — the image's own range is degenerate
   (``end_paragraph < start_paragraph``); the extraction evidence is
   corrupt and the image should be re-extracted, not placed.
2. ``ambiguous-question-ranges`` — two or more question ranges fully
   contain the image (duplicated or overlapping question segmentation);
   the layout itself cannot name one owner.
3. ``straddles-question-boundary`` — the image touches two or more
   question ranges, or hangs past the only range it meets; a human must
   decide where the boundary cut falls.
4. Full containment by exactly one question range maps the image to that
   question with ``field="stem"`` and ``role="figure"`` — the neutral
   defaults, because paragraph ranges alone carry no finer signal.
5. ``outside-all-questions`` — the image meets no question range at all
   (front matter, headers, or the gap between questions).

An unknown placement sets ``question_id`` to ``None`` exactly when it
sets ``reason``, and its ``evidence`` still records the image range plus
every question range involved in the refusal, so a reviewer can audit
the decision without re-running inference. Degenerate question ranges
(``end_paragraph < start_paragraph``) touch nothing and are inert.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

IMAGE_PLACEMENT_VERSION = "image-placement/1"

REASON_STRADDLES_QUESTION_BOUNDARY = "straddles-question-boundary"
REASON_OUTSIDE_ALL_QUESTIONS = "outside-all-questions"
REASON_AMBIGUOUS_QUESTION_RANGES = "ambiguous-question-ranges"
REASON_INVALID_RANGE = "invalid-range"

DEFAULT_FIELD = "stem"
DEFAULT_ROLE = "figure"

_REASONS = frozenset(
    {
        REASON_STRADDLES_QUESTION_BOUNDARY,
        REASON_OUTSIDE_ALL_QUESTIONS,
        REASON_AMBIGUOUS_QUESTION_RANGES,
        REASON_INVALID_RANGE,
    }
)

_PLACEMENT_FIELDS = {"question_id", "field", "role", "evidence", "reason"}
_REPORT_FIELDS = {"placements"}


@dataclass(frozen=True, slots=True)
class ImagePlacement:
    """One image's placement decision with its paragraph-range proof.

    A mapped placement names the owning ``question_id`` plus the default
    ``field`` and ``role`` labels, and its ``evidence`` carries both the
    image range and the question range that proves containment. An
    unknown placement sets ``question_id`` to ``None`` and carries
    exactly one machine-readable ``reason``; its evidence still records
    the image range and every question range involved in the refusal.
    """

    question_id: str | None
    field: str | None
    role: str | None
    evidence: tuple[dict[str, Any], ...]
    reason: str | None

    @property
    def known(self) -> bool:
        return self.question_id is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "field": self.field,
            "role": self.role,
            "evidence": [dict(item) for item in self.evidence],
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImagePlacement:
        unknown = sorted(set(data) - _PLACEMENT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown image-placement field(s): {', '.join(unknown)}.")
        question_id = data["question_id"]
        field = data["field"]
        role = data["role"]
        reason = data["reason"]
        if question_id is not None:
            question_id = str(question_id)
        if field is not None:
            field = str(field)
        if role is not None:
            role = str(role)
        if reason is not None:
            reason = str(reason)
            if reason not in _REASONS:
                raise ValueError(f"Unsupported image-placement reason: {reason!r}.")
        if (question_id is None) != (reason is not None):
            raise ValueError(
                "An image placement carries a reason exactly when its question "
                "is unknown."
            )
        if question_id is None and (field is not None or role is not None):
            raise ValueError("An unknown image placement carries no field or role.")
        if question_id is not None and (field is None or role is None):
            raise ValueError("A mapped image placement requires a field and a role.")
        return cls(
            question_id=question_id,
            field=field,
            role=role,
            evidence=tuple(dict(item) for item in data["evidence"]),
            reason=reason,
        )


@dataclass(frozen=True, slots=True)
class ImagePlacementReport:
    """Placements for one import batch, one per image in input order.

    The report never reorders, drops, or merges images: the i-th
    placement is the decision for the i-th input image, including the
    unknowns, so a caller can always zip results back onto its inputs.
    """

    placements: tuple[ImagePlacement, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"placements": [item.to_dict() for item in self.placements]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImagePlacementReport:
        unknown = sorted(set(data) - _REPORT_FIELDS)
        if unknown:
            raise ValueError(
                f"Unknown image-placement-report field(s): {', '.join(unknown)}."
            )
        return cls(
            placements=tuple(
                ImagePlacement.from_dict(item) for item in data["placements"]
            )
        )


def _normalize_question(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "question_id": str(item["question_id"]),
        "start_paragraph": int(item["start_paragraph"]),
        "end_paragraph": int(item["end_paragraph"]),
    }


def _normalize_image(item: Mapping[str, Any]) -> dict[str, Any]:
    record = {
        "image_id": str(item["image_id"]),
        "start_paragraph": int(item["start_paragraph"]),
        "end_paragraph": int(item["end_paragraph"]),
    }
    page = item.get("page")
    if page is not None:
        record["page"] = int(page)
    return record


def _image_evidence(image: Mapping[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "kind": "image-range",
        "image_id": image["image_id"],
        "start_paragraph": image["start_paragraph"],
        "end_paragraph": image["end_paragraph"],
    }
    if image.get("page") is not None:
        record["page"] = image["page"]
    return record


def _question_evidence(question: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "question-range",
        "question_id": question["question_id"],
        "start_paragraph": question["start_paragraph"],
        "end_paragraph": question["end_paragraph"],
    }


def _ranges_touch(image: Mapping[str, Any], question: Mapping[str, Any]) -> bool:
    """True when the inclusive paragraph ranges share at least one paragraph."""
    start = max(image["start_paragraph"], question["start_paragraph"])
    end = min(image["end_paragraph"], question["end_paragraph"])
    return start <= end


def _question_covers(image: Mapping[str, Any], question: Mapping[str, Any]) -> bool:
    """True when the question's range fully covers the image's range."""
    return (
        question["start_paragraph"] <= image["start_paragraph"]
        and image["end_paragraph"] <= question["end_paragraph"]
    )


def _unknown(reason: str, evidence: tuple[dict[str, Any], ...]) -> ImagePlacement:
    return ImagePlacement(
        question_id=None,
        field=None,
        role=None,
        evidence=evidence,
        reason=reason,
    )


def _place_image(
    image: Mapping[str, Any],
    questions: Sequence[Mapping[str, Any]],
) -> ImagePlacement:
    image_record = _image_evidence(image)
    if image["end_paragraph"] < image["start_paragraph"]:
        return _unknown(REASON_INVALID_RANGE, (image_record,))

    intersecting = tuple(q for q in questions if _ranges_touch(image, q))
    containing = tuple(q for q in questions if _question_covers(image, q))

    if len(containing) > 1:
        return _unknown(
            REASON_AMBIGUOUS_QUESTION_RANGES,
            (image_record, *(_question_evidence(q) for q in containing)),
        )
    if len(intersecting) > 1:
        return _unknown(
            REASON_STRADDLES_QUESTION_BOUNDARY,
            (image_record, *(_question_evidence(q) for q in intersecting)),
        )
    if containing:
        question = containing[0]
        return ImagePlacement(
            question_id=question["question_id"],
            field=DEFAULT_FIELD,
            role=DEFAULT_ROLE,
            evidence=(image_record, _question_evidence(question)),
            reason=None,
        )
    if intersecting:
        return _unknown(
            REASON_STRADDLES_QUESTION_BOUNDARY,
            (image_record, _question_evidence(intersecting[0])),
        )
    return _unknown(REASON_OUTSIDE_ALL_QUESTIONS, (image_record,))


def infer_image_placements(
    images: Sequence[Mapping[str, Any]],
    question_ranges: Sequence[Mapping[str, Any]],
) -> ImagePlacementReport:
    """Map each image onto a question, or refuse with a machine-readable reason.

    ``images`` are ``{image_id, start_paragraph, end_paragraph, page?}``
    records with inclusive integer paragraph ranges; ``question_ranges``
    are ordered ``{question_id, start_paragraph, end_paragraph}`` records
    that the caller promises are non-overlapping (overlaps are still
    handled conservatively, as ambiguity). The function is pure: no I/O,
    no mutation, and identical output for identical input. The returned
    report keeps one placement per input image, in input order.
    """
    questions = tuple(_normalize_question(item) for item in question_ranges)
    placements = tuple(
        _place_image(_normalize_image(item), questions) for item in images
    )
    return ImagePlacementReport(placements=placements)
