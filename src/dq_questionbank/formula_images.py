"""Candidate records for formula images that need manual transcription.

Imported documents sometimes carry formulas as raster images. The public
answer is deliberately **not** bundled OCR: this module produces a
candidate record that tells a reviewer exactly which image needs
transcription and keeps the evidence attached until a human provides the
LaTeX.

- :func:`detect_formula_image_candidates` binds every image block the
  source pipeline explicitly flagged with ``metadata.formula_image`` to
  the asset reference and SHA-256 digest recorded on the question. The
  flag is the deterministic signal; no OCR engine, external service, or
  network access is used or required.
- :func:`fill_transcription` records the human transcription and its
  contributor, and fails closed when the asset is missing or its digest
  no longer matches the one bound at detection time.

The serialized record is the review-item shape: a reviewer sees the
question field, the image evidence, and an empty ``latex`` slot until
they fill it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from .models import Question

FORMULA_IMAGE_FLAG = "formula_image"
STATUS_PENDING = "pending"
STATUS_TRANSCRIBED = "transcribed"
_STATUSES = (STATUS_PENDING, STATUS_TRANSCRIBED)

_CANDIDATE_FIELDS = {
    "question_id",
    "target_field",
    "asset_id",
    "asset_uri",
    "asset_sha256",
    "latex",
    "transcribed_by",
    "status",
}

_BLOCK_PATH_RE = re.compile(r"^(stem|solution)\.blocks\[(\d+)\]$")


@dataclass(frozen=True, slots=True)
class FormulaImageCandidate:
    """One formula image waiting for a human transcription.

    ``latex`` starts empty; ``fill_transcription`` fills it and records
    the contributor as the transcription source while the image stays
    attached as evidence through ``asset_id``/``asset_uri`` and the
    digest bound at detection time.
    """

    question_id: str
    target_field: str
    asset_id: str
    asset_uri: str
    asset_sha256: str
    latex: str = ""
    transcribed_by: str | None = None
    status: str = STATUS_PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "target_field": self.target_field,
            "asset_id": self.asset_id,
            "asset_uri": self.asset_uri,
            "asset_sha256": self.asset_sha256,
            "latex": self.latex,
            "transcribed_by": self.transcribed_by,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FormulaImageCandidate:
        unknown = sorted(set(data) - _CANDIDATE_FIELDS)
        if unknown:
            raise ValueError(
                f"Unknown formula-image candidate field(s): {', '.join(unknown)}."
            )
        status = str(data["status"])
        if status not in _STATUSES:
            raise ValueError(f"Unsupported candidate status: {status!r}.")
        if status == STATUS_TRANSCRIBED and (not data["latex"] or not data["transcribed_by"]):
            raise ValueError("A transcribed candidate requires latex and transcribed_by.")
        return cls(
            question_id=str(data["question_id"]),
            target_field=str(data["target_field"]),
            asset_id=str(data["asset_id"]),
            asset_uri=str(data["asset_uri"]),
            asset_sha256=str(data["asset_sha256"]),
            latex=str(data.get("latex", "")),
            transcribed_by=data.get("transcribed_by"),
            status=status,
        )


def _iter_flagged_image_blocks(question: Question):
    for field_name in ("stem", "solution"):
        content = getattr(question, field_name, None)
        for index, block in enumerate(content.blocks if content else []):
            if block.type == "image" and block.metadata.get(FORMULA_IMAGE_FLAG) is True:
                yield f"{field_name}.blocks[{index}]", block


def detect_formula_image_candidates(question: Question) -> list[FormulaImageCandidate]:
    """Bind every flagged formula image to its asset evidence.

    Only image blocks the source pipeline explicitly flagged with
    ``metadata.formula_image: true`` become candidates, and only when the
    referenced asset exists and carries a SHA-256 digest — a record
    without bound evidence cannot be reviewed. Unflagged images and
    digest-less assets are left alone.
    """
    assets = {asset.id: asset for asset in question.assets or []}
    candidates: list[FormulaImageCandidate] = []
    for path, block in _iter_flagged_image_blocks(question):
        if not block.asset_id:
            continue
        asset = assets.get(block.asset_id)
        if asset is None or not asset.sha256:
            continue
        candidates.append(
            FormulaImageCandidate(
                question_id=question.id,
                target_field=path,
                asset_id=asset.id,
                asset_uri=asset.uri,
                asset_sha256=asset.sha256,
            )
        )
    return candidates


def fill_transcription(
    candidate: FormulaImageCandidate,
    question: Question,
    latex: str,
    contributor: str,
) -> FormulaImageCandidate:
    """Record a human transcription for a candidate, failing closed.

    The transcription is only accepted while the question still carries
    the exact asset the candidate was bound to: a missing asset or a
    changed digest raises ``ValueError`` instead of silently detaching
    the evidence.
    """
    if not latex.strip():
        raise ValueError("A transcription requires non-empty LaTeX.")
    if not contributor.strip():
        raise ValueError("A transcription requires a named contributor.")
    if not _BLOCK_PATH_RE.match(candidate.target_field):
        raise ValueError(f"Unsupported candidate field path: {candidate.target_field!r}.")
    if candidate.status != STATUS_PENDING:
        raise ValueError("Only a pending candidate can receive a transcription.")
    assets = {asset.id: asset for asset in question.assets or []}
    asset = assets.get(candidate.asset_id)
    if asset is None:
        raise ValueError(
            f"Asset {candidate.asset_id!r} is no longer present on the question."
        )
    if asset.sha256 != candidate.asset_sha256:
        raise ValueError(
            f"Asset {candidate.asset_id!r} digest changed since detection; "
            "re-run detection before transcribing."
        )
    return replace(
        candidate,
        latex=latex,
        transcribed_by=contributor,
        status=STATUS_TRANSCRIBED,
    )

