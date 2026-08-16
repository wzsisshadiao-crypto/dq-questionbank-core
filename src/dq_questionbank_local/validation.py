"""Application boundary validation backed by the public core model."""

from __future__ import annotations

from typing import Any

from dq_questionbank.models import QuestionSet
from dq_questionbank.validation import validate_question_set as validate_core_question_set


class ValidationError(ValueError):
    """Raised when a payload cannot safely enter the local workspace."""


def validate_question_set(payload: Any) -> dict[str, Any]:
    """Validate canonical input without discarding extension fields."""
    if not isinstance(payload, dict):
        raise ValidationError("A question set must be a JSON object.")
    try:
        question_set = QuestionSet.from_dict(payload)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Question set could not be parsed as canonical JSON.") from exc
    issues = [issue for issue in validate_core_question_set(question_set) if issue.severity == "error"]
    if issues:
        first = issues[0]
        raise ValidationError(f"{first.path}: {first.message}")
    return payload
