"""Application boundary validation backed by the public core model."""

from __future__ import annotations

from typing import Any

from dq_questionbank.validation import validate_with_schema


class ValidationError(ValueError):
    """Raised when a payload cannot safely enter the local workspace."""


def validate_question_set(payload: Any) -> dict[str, Any]:
    """Validate canonical input without discarding extension fields."""
    if not isinstance(payload, dict):
        raise ValidationError("A question set must be a JSON object.")
    issues = [issue for issue in validate_with_schema(payload) if issue.severity == "error"]
    if issues:
        first = issues[0]
        raise ValidationError(f"{first.path}: {first.message}")
    return payload
