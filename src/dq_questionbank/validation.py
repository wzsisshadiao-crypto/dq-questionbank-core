"""Validation rules for the canonical question model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import urlparse

from .models import (
    BLOCK_TYPES,
    QUESTION_TYPES,
    SUPPORTED_SCHEMA_VERSIONS,
    Content,
    Question,
    QuestionSet,
)

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
    if question.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        issues.append(
            ValidationIssue(
                f"{path}.schema_version",
                "unsupported_schema",
                "Expected schema version " + " or ".join(SUPPORTED_SCHEMA_VERSIONS) + ".",
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
    if question.difficulty is not None:
        difficulty = question.difficulty
        if (
            isinstance(difficulty, bool)
            or not isinstance(difficulty, (int, float))
            or not 0 <= difficulty <= 1
        ):
            issues.append(
                ValidationIssue(
                    f"{path}.difficulty",
                    "invalid_difficulty",
                    "Difficulty must be a number between 0 and 1.",
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
    if question.analysis:
        issues.extend(_content_issues(question.analysis, f"{path}.analysis", set(asset_ids)))
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
    if question_set.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        issues.append(
            ValidationIssue(
                "schema_version",
                "unsupported_schema",
                "Expected schema version " + " or ".join(SUPPORTED_SCHEMA_VERSIONS) + ".",
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


def _matches_schema_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _resolve_local_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"Unsupported non-local schema reference: {reference}")
    current: Any = root
    for part in reference[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        current = current[key]
    if not isinstance(current, dict):
        raise ValueError(f"Schema reference does not resolve to an object: {reference}")
    return current


def _stdlib_schema_issues(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    path: str = "$",
) -> list[ValidationIssue]:
    if "$ref" in schema:
        return _stdlib_schema_issues(value, _resolve_local_ref(root, schema["$ref"]), root, path)
    issues: list[ValidationIssue] = []
    expected = schema.get("type")
    if isinstance(expected, str) and not _matches_schema_type(value, expected):
        return [ValidationIssue(path, "schema", f"Expected {expected}.", "error")]
    if "const" in schema and value != schema["const"]:
        issues.append(ValidationIssue(path, "schema", f"Expected {schema['const']!r}.", "error"))
    if "enum" in schema and value not in schema["enum"]:
        issues.append(ValidationIssue(path, "schema", "Value is not in the allowed set.", "error"))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                issues.append(
                    ValidationIssue(f"{path}/{key}", "schema", "Required property is missing.", "error")
                )
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                issues.append(
                    ValidationIssue(f"{path}/{key}", "schema", "Unexpected property.", "error")
                )
        for key, child in properties.items():
            if key in value:
                issues.extend(_stdlib_schema_issues(value[key], child, root, f"{path}/{key}"))
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                issues.extend(_stdlib_schema_issues(item, item_schema, root, f"{path}/{index}"))
        if schema.get("uniqueItems") is True:
            encoded = [repr(item) for item in value]
            if len(encoded) != len(set(encoded)):
                issues.append(ValidationIssue(path, "schema", "Array items must be unique.", "error"))
    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            issues.append(ValidationIssue(path, "schema", "String is too short.", "error"))
        if isinstance(schema.get("pattern"), str) and re.search(schema["pattern"], value) is None:
            issues.append(ValidationIssue(path, "schema", "String does not match the pattern.", "error"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            issues.append(ValidationIssue(path, "schema", "Number is below the minimum.", "error"))
        if "maximum" in schema and value > schema["maximum"]:
            issues.append(ValidationIssue(path, "schema", "Number is above the maximum.", "error"))
    return issues


def validate_with_schema(
    payload: dict[str, Any],
    schema: dict | None = None,
) -> list[ValidationIssue]:
    """Run JSON Schema structural validation followed by semantic rules.

    Returns a combined list; schema validation failures do not prevent semantic checks.
    """
    issues: list[ValidationIssue] = []
    if schema is None:
        declared = payload.get("schema_version") if isinstance(payload, dict) else None
        if declared is None:
            version = "1.0"  # Structural validation reports the missing field.
        elif declared in SUPPORTED_SCHEMA_VERSIONS:
            version = declared
        else:
            version = None
            issues.append(
                ValidationIssue(
                    "schema_version",
                    "unsupported_schema",
                    f"Payload declares schema_version {declared!r}; expected one of: "
                    + ", ".join(SUPPORTED_SCHEMA_VERSIONS)
                    + ".",
                )
            )
        if version is not None:
            try:
                from .schema import load_schema
                schema = load_schema(version)
            except Exception as exc:
                issues.append(
                    ValidationIssue("$", "schema_unavailable", str(exc), "error")
                )
                schema = None
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
            issues.extend(_stdlib_schema_issues(payload, schema, schema))
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
