"""Group PDF chunks into auditable worksets with recall verification.

Splitting a 40-page paper into per-question chunks is only useful when a
run can PROVE nothing was lost: every question in the source must be
claimed by exactly one chunk, no more, no less. This module groups chunks
into small reviewable batches (worksets) and verifies that recall against
an expected question count - the number the paper itself claims. Part of
#89.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .pdf_splitter import PdfSplitResult

PDF_WORKSET_VERSION = "pdf-workset/1"

REASON_NOTHING_TO_BATCH = "nothing-to-batch"

_PLAN_FIELDS = {"version", "worksets", "reasons"}
_WORKSET_FIELDS = {"workset_id", "question_keys"}
_RECALL_FIELDS = {
    "version",
    "expected_count",
    "found_count",
    "duplicate_keys",
    "missing_count",
    "ok",
}


@dataclass(frozen=True, slots=True)
class Workset:
    """One small, auditable batch of question keys."""

    workset_id: str
    question_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workset_id": self.workset_id,
            "question_keys": list(self.question_keys),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workset:
        unknown = sorted(set(data) - _WORKSET_FIELDS)
        if unknown:
            raise ValueError(f"Unknown workset field(s): {', '.join(unknown)}.")
        return cls(
            workset_id=str(data["workset_id"]),
            question_keys=tuple(str(item) for item in data["question_keys"]),
        )


@dataclass(frozen=True, slots=True)
class WorksetPlan:
    """An ordered grouping of all chunk keys into worksets."""

    worksets: tuple[Workset, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PDF_WORKSET_VERSION,
            "worksets": [workset.to_dict() for workset in self.worksets],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorksetPlan:
        unknown = sorted(set(data) - _PLAN_FIELDS)
        if unknown:
            raise ValueError(f"Unknown workset-plan field(s): {', '.join(unknown)}.")
        if str(data.get("version", PDF_WORKSET_VERSION)) != PDF_WORKSET_VERSION:
            raise ValueError(f"Unsupported workset version: {data['version']!r}.")
        return cls(
            worksets=tuple(Workset.from_dict(item) for item in data["worksets"]),
            reasons=tuple(str(item) for item in data["reasons"]),
        )


def build_worksets(split_result: PdfSplitResult, batch_size: int = 3) -> WorksetPlan:
    """Group chunk keys into ordered worksets of at most ``batch_size`` (pure).

    Keys keep their document order, so workset 1 always holds the first
    questions. A split result with no chunks yields an empty plan with one
    canonical reason instead of a misleading empty batch.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be a positive integer.")
    keys = [chunk.question_key for chunk in split_result.chunks]
    if not keys:
        return WorksetPlan((), (REASON_NOTHING_TO_BATCH,))
    worksets: list[Workset] = []
    for start in range(0, len(keys), batch_size):
        batch = keys[start : start + batch_size]
        worksets.append(
            Workset(workset_id=f"ws-{len(worksets) + 1}", question_keys=tuple(batch))
        )
    return WorksetPlan(worksets=tuple(worksets), reasons=())



@dataclass(frozen=True, slots=True)
class RecallReport:
    """Proof that every source question is claimed by exactly one chunk.

    ``ok`` is true only when no key is double-claimed and, when an expected
    count is given, the number of distinct found keys equals it.
    """

    expected_count: int | None
    found_count: int
    duplicate_keys: tuple[str, ...]
    missing_count: int
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PDF_WORKSET_VERSION,
            "expected_count": self.expected_count,
            "found_count": self.found_count,
            "duplicate_keys": list(self.duplicate_keys),
            "missing_count": self.missing_count,
            "ok": self.ok,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecallReport:
        unknown = sorted(set(data) - _RECALL_FIELDS)
        if unknown:
            raise ValueError(f"Unknown recall-report field(s): {', '.join(unknown)}.")
        expected = data["expected_count"]
        return cls(
            expected_count=int(expected) if expected is not None else None,
            found_count=int(data["found_count"]),
            duplicate_keys=tuple(str(item) for item in data["duplicate_keys"]),
            missing_count=int(data["missing_count"]),
            ok=bool(data["ok"]),
        )


def verify_recall(
    split_result: PdfSplitResult, expected_count: int | None = None
) -> RecallReport:
    """Verify full coverage with no double-claims (pure, deterministic).

    Duplicates are keys claimed by more than one chunk (a split that
    doubled a question); missing_count is how far below the expected count
    the distinct keys fall. With no expected count the report still proves
    the no-double-claim half of recall.
    """
    if expected_count is not None and expected_count < 0:
        raise ValueError("expected_count must not be negative.")
    counts = Counter(chunk.question_key for chunk in split_result.chunks)
    duplicates = tuple(sorted(key for key, count in counts.items() if count > 1))
    found = len(counts)
    missing = max(0, expected_count - found) if expected_count is not None else 0
    ok = not duplicates and (expected_count is None or found == expected_count)
    return RecallReport(
        expected_count=expected_count,
        found_count=found,
        duplicate_keys=duplicates,
        missing_count=missing,
        ok=ok,
    )
