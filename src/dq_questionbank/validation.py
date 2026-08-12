"""Validation rules for the canonical question model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlparse

from .models import BLOCK_TYPES, QUESTION_TYPES, SCHEMA_VERSION, Content, Question, QuestionSet

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    code: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


def _content_issues(content: Content, path: str, asset_ids: set[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, block in enumerate(content.blocks):
        block_path = f"{path}.blocks[{index}]"
        if block.type not in BLOCK_TYPES:
            issues.append(
                ValidationIssue(
                    f"{block_path}.type", "unsupported_block", "Unsupported content block type."
                )
            )
        if block.type in {"text", "code"} and block.text is None:
            issues.append(
                ValidationIssue(block_path, "missing_text", "Text and code blocks require text.")
            )
        if block.type == "math" and not (block.latex or "").strip():
            issues.append(
                ValidationIssue(block_path, "missing_latex", "Math blocks require LaTeX.")
            )
        if block.type == "image":
            if not block.asset_id:
                issues.append(
                    ValidationIssue(
                        block_path, "missing_asset_id", "Image blocks require asset_id."
                    )
                )
            elif block.asset_id not in asset_ids:
                issues.append(
                    ValidationIssue(
                        block_path, "unknown_asset", "Image block references an unknown asset."
                    )
                )
        if block.type == "table" and not block.rows:
            issues.append(
                ValidationIssue(block_path, "empty_table", "Table blocks require at least one row.")
            )
    return issues


def _asset_uri_is_safe(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme:
        return parsed.scheme in {"https", "data"}
    if PureWindowsPath(uri).is_absolute() or PurePosixPath(uri).is_absolute():
        return False
    return ".." not in PurePosixPath(uri.replace("\\", "/")).parts


def validate_question(question: Question, path: str = "question") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if question.schema_version != SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                f"{path}.schema_version",
                "unsupported_schema",
                f"Expected schema version {SCHEMA_VERSION}.",
            )
        )
    if not question.id.strip():
        issues.append(ValidationIssue(f"{path}.id", "missing_id", "Question id is required."))
    if question.type not in QUESTION_TYPES:
        issues.append(
            ValidationIssue(
                f"{path}.type", "unsupported_question_type", "Unsupported question type."
            )
        )
    if not LANGUAGE_RE.match(question.language):
        issues.append(
            ValidationIssue(
                f"{path}.language", "invalid_language", "Use a BCP 47-style language tag."
            )
        )
    if not question.stem.blocks and question.type != "composite":
        issues.append(
            ValidationIssue(f"{path}.stem", "empty_stem", "Question stem must not be empty.")
        )
    if question.difficulty is not None and not 0 <= float(question.difficulty) <= 1:
        issues.append(
            ValidationIssue(
                f"{path}.difficulty", "invalid_difficulty", "Difficulty must be between 0 and 1."
            )
        )

    asset_ids = [asset.id for asset in question.assets]
    if len(asset_ids) != len(set(asset_ids)):
        issues.append(
            ValidationIssue(
                f"{path}.assets",
                "duplicate_asset_id",
                "Asset ids must be unique within a question.",
            )
        )
    for index, asset in enumerate(question.assets):
        asset_path = f"{path}.assets[{index}]"
        if not asset.id.strip() or not asset.uri.strip():
            issues.append(
                ValidationIssue(asset_path, "invalid_asset", "Asset id and uri are required.")
            )
        elif not _asset_uri_is_safe(asset.uri):
            issues.append(
                ValidationIssue(
                    f"{asset_path}.uri",
                    "unsafe_asset_uri",
                    "Use a relative path, HTTPS URL, or data URI.",
                )
            )
        if asset.sha256 and not SHA256_RE.match(asset.sha256):
            issues.append(
                ValidationIssue(
                    f"{asset_path}.sha256",
                    "invalid_sha256",
                    "sha256 must contain 64 lowercase hexadecimal characters.",
                )
            )

    issues.extend(_content_issues(question.stem, f"{path}.stem", set(asset_ids)))
    if question.solution:
        issues.extend(_content_issues(question.solution, f"{path}.solution", set(asset_ids)))
    for index, hint in enumerate(question.hints):
        issues.extend(_content_issues(hint, f"{path}.hints[{index}]", set(asset_ids)))

    choice_ids = [choice.id for choice in question.choices]
    if len(choice_ids) != len(set(choice_ids)):
        issues.append(
            ValidationIssue(f"{path}.choices", "duplicate_choice_id", "Choice ids must be unique.")
        )
    if question.type in {"single_choice", "multiple_choice"} and len(question.choices) < 2:
        issues.append(
            ValidationIssue(
                f"{path}.choices",
                "insufficient_choices",
                "Choice questions require at least two choices.",
            )
        )
    for index, choice in enumerate(question.choices):
        issues.extend(
            _content_issues(choice.content, f"{path}.choices[{index}].content", set(asset_ids))
        )
    if question.answer and question.answer.kind in {"choice", "choices"}:
        values = (
            question.answer.value
            if isinstance(question.answer.value, list)
            else [question.answer.value]
        )
        missing = sorted(str(value) for value in values if str(value) not in set(choice_ids))
        if missing:
            issues.append(
                ValidationIssue(
                    f"{path}.answer.value",
                    "unknown_choice",
                    f"Answer references unknown choices: {', '.join(missing)}.",
                )
            )

    sub_ids = [item.id for item in question.subquestions]
    if len(sub_ids) != len(set(sub_ids)):
        issues.append(
            ValidationIssue(
                f"{path}.subquestions",
                "duplicate_subquestion_id",
                "Subquestion ids must be unique.",
            )
        )
    for index, subquestion in enumerate(question.subquestions):
        issues.extend(validate_question(subquestion, f"{path}.subquestions[{index}]"))
    return issues


def validate_question_set(question_set: QuestionSet) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if question_set.schema_version != SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                "schema_version", "unsupported_schema", f"Expected schema version {SCHEMA_VERSION}."
            )
        )
    if not question_set.id.strip():
        issues.append(ValidationIssue("id", "missing_id", "Question set id is required."))
    if not question_set.title.strip():
        issues.append(ValidationIssue("title", "missing_title", "Question set title is required."))
    ids = [question.id for question in question_set.questions]
    if len(ids) != len(set(ids)):
        issues.append(
            ValidationIssue(
                "questions", "duplicate_question_id", "Top-level question ids must be unique."
            )
        )
    for index, question in enumerate(question_set.questions):
        issues.extend(validate_question(question, f"questions[{index}]"))
    return issues
def validate_with_schema(
    payload: dict,
    schema: dict | None = None,
) -> list[ValidationIssue]:
    """Run JSON Schema structural validation followed by semantic rules.

    Returns a combined list; schema validation failures do not prevent semantic checks.
    """
    issues: list[ValidationIssue] = []
    if schema is None:
        try:
            from .schema import load_schema
            schema = load_schema()
        except Exception:
            pass
    if schema is not None:
        try:
            import jsonschema
            validator = jsonschema.Draft202012Validator(schema)
            for error in validator.iter_errors(payload):
                issues.append(
                    ValidationIssue(
                        "/".join(str(p) for p in error.absolute_path),
                        "schema",
                        error.message,
                        "error",
                    )
                )
        except ImportError:
            pass
        except Exception as exc:
            issues.append(
                ValidationIssue("$", "schema_error", str(exc), "error")
            )
    try:
        from .models import QuestionSet
        question_set = QuestionSet.from_dict(payload)
        issues.extend(validate_question_set(question_set))
    except Exception as exc:
        issues.append(
            ValidationIssue("$", "model_parse_error", str(exc), "error")
        )
    return issues
