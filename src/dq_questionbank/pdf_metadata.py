"""Explicit paper metadata contract for imported question volumes.

Bulk import volumes describe exactly one paper: every question in a batch
must agree on subject, question type, source label, and grade. Ambiguous
or per-question-divergent metadata is the classic root cause of mis-filed
exams, so the contract fails closed instead of guessing.

The default question-type vocabulary
(:data:`PAPER_QUESTION_TYPES`) is the neutral reference set; deployments
with a localized or richer controlled vocabulary pass their own
``allowed_question_types`` to :func:`canonical_paper_metadata`.

Example::

    metadata = canonical_paper_metadata(
        subject="mathematical analysis",
        question_type="exam",
        source="2026 University A (analysis)",
    )
    metadata_from_questions(cards["questions"]) == metadata  # True or raises
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

from .exceptions import QuestionBankError

PDF_METADATA_SCHEMA = "pdf-paper-metadata/v1"

#: Controlled vocabulary of the reference deployment. Shared across a whole
#: volume; per-question values must match exactly. A tuple (not a set) so
#: the value stays stable across processes and in the public API manifest.
PAPER_QUESTION_TYPES = ("exam", "mock", "textbook", "term")

METADATA_FIELDS = ("subject", "question_type", "source", "grade")


class PaperMetadataError(QuestionBankError):
    """A paper volume cannot proceed without explicit, consistent metadata."""


def canonical_paper_metadata(
    *,
    subject: str,
    question_type: str,
    source: str,
    grade: str = "",
    allowed_question_types: Collection[str] = PAPER_QUESTION_TYPES,
) -> dict:
    """Validate and normalize one paper's metadata into its canonical form.

    All values are stripped; ``subject``, ``question_type`` (inside the
    allowed vocabulary), and ``source`` are required, ``grade`` is optional.
    """
    values = {
        "subject": str(subject or "").strip(),
        "question_type": str(question_type or "").strip(),
        "source": str(source or "").strip(),
        "grade": str(grade or "").strip(),
    }
    if not values["subject"]:
        raise PaperMetadataError("paper subject is required")
    if values["question_type"] not in allowed_question_types:
        raise PaperMetadataError(
            "paper question_type must be explicitly one of: "
            + ", ".join(sorted(allowed_question_types))
        )
    if not values["source"]:
        raise PaperMetadataError("paper source is required")
    return {"schema": PDF_METADATA_SCHEMA, **values}


def metadata_from_questions(
    questions: Iterable[dict],
    allowed_question_types: Collection[str] = PAPER_QUESTION_TYPES,
) -> dict:
    """Derive the paper metadata from a question list and enforce agreement.

    Every question must carry the same metadata fields; the first question
    defines the expectation and any divergence raises
    :class:`PaperMetadataError` naming the offending index.
    """
    rows = list(questions or [])
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise PaperMetadataError("question list must be non-empty objects")
    first = rows[0]
    metadata = canonical_paper_metadata(
        subject=first.get("subject"),
        question_type=first.get("question_type"),
        source=first.get("source"),
        grade=first.get("grade"),
        allowed_question_types=allowed_question_types,
    )
    expected = {field: metadata[field] for field in METADATA_FIELDS}
    for index, row in enumerate(rows):
        actual = {
            field: str(row.get(field) or "").strip()
            for field in METADATA_FIELDS
        }
        if actual != expected:
            raise PaperMetadataError(
                f"paper metadata mismatch at question index {index}: "
                f"expected={expected!r}, actual={actual!r}"
            )
    return metadata


def assert_metadata_matches(actual: dict, expected: dict, *, label: str = "metadata") -> dict:
    """Assert a recorded metadata block equals the canonical expectation."""
    expected_metadata = canonical_paper_metadata(
        subject=expected.get("subject"),
        question_type=expected.get("question_type"),
        source=expected.get("source"),
        grade=expected.get("grade"),
    )
    actual_values = {
        field: str(actual.get(field) or "").strip()
        for field in METADATA_FIELDS
    }
    expected_values = {
        field: expected_metadata[field] for field in METADATA_FIELDS
    }
    if actual_values != expected_values:
        raise PaperMetadataError(
            f"{label} mismatch: expected={expected_values!r}, "
            f"actual={actual_values!r}"
        )
    return expected_metadata


__all__ = [
    "METADATA_FIELDS",
    "PAPER_QUESTION_TYPES",
    "PDF_METADATA_SCHEMA",
    "PaperMetadataError",
    "assert_metadata_matches",
    "canonical_paper_metadata",
    "metadata_from_questions",
]
