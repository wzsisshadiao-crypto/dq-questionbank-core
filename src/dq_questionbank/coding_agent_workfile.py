"""The coding-agent import work-file contract.

A coding agent with workspace access imports questions by editing a JSON
work file: it reads the evidence, transcribes each question's text fields,
and walks every ``work_status`` from ``pending_transcription`` to
``transcribed`` (or ``needs_review`` when the evidence is ambiguous). The
deterministic pipeline — not the agent — owns question identity, evidence
bindings, and publication.

This module guards that division of labour without touching a database:

- :func:`validate_work_file` returns human-readable findings for every
  contract violation (schema tag, duplicate numbering, unknown statuses,
  missing text, forbidden pipeline-owned fields),
- :func:`transition_work_status` applies only the status transitions the
  transcription loop actually uses and never mutates its input,
- :func:`write_work_file` publishes the file atomically so a reader never
  observes a partially written work file, and
- :func:`read_work_file` tolerates a UTF-8 BOM added by editors.

Example::

    findings = validate_work_file(payload)
    if findings:
        raise SystemExit("\\n".join(findings))
    payload = transition_work_status(payload, "3.2", WORK_STATUS_TRANSCRIBED)
    write_work_file(path, payload)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CODING_AGENT_WORKFILE_SCHEMA = "coding-agent-workfile/v1"

WORK_STATUS_PENDING = "pending_transcription"
WORK_STATUS_TRANSCRIBED = "transcribed"
WORK_STATUS_NEEDS_REVIEW = "needs_review"
WORK_STATUSES = (
    WORK_STATUS_PENDING,
    WORK_STATUS_TRANSCRIBED,
    WORK_STATUS_NEEDS_REVIEW,
)

#: Fields the agent transcribes. ``body`` and ``answer`` must be finished
#: before a question may reach ``transcribed``.
TEXT_FIELDS = ("body", "answer", "explanation")

#: Pipeline-owned fields that must never appear in the agent-edited file:
#: identity, evidence binding, and runtime bookkeeping belong to the
#: dispatcher, the finalize stage, and the postflight scanner.
FORBIDDEN_WORKFILE_FIELDS = (
    "schema",
    "job_id",
    "workset_id",
    "run_id",
    "question_id",
    "evidence_dir",
    "evidence_pages",
    "evidence_sha256",
    "complete",
    "cards",
)

_ALLOWED_TRANSITIONS = {
    (WORK_STATUS_PENDING, WORK_STATUS_TRANSCRIBED),
    (WORK_STATUS_PENDING, WORK_STATUS_NEEDS_REVIEW),
    (WORK_STATUS_TRANSCRIBED, WORK_STATUS_NEEDS_REVIEW),
    (WORK_STATUS_NEEDS_REVIEW, WORK_STATUS_TRANSCRIBED),
}


def _question_number(question: dict) -> str:
    value = question.get("question_number")
    return str(value) if value is not None else ""


def validate_work_file(payload: object) -> list[str]:
    """Return a deterministic list of contract violations (empty when valid)."""
    findings: list[str] = []
    if not isinstance(payload, dict):
        return ["work file must be a JSON object"]
    if payload.get("schema") != CODING_AGENT_WORKFILE_SCHEMA:
        findings.append(
            f"schema must be {CODING_AGENT_WORKFILE_SCHEMA!r}, "
            f"got {payload.get('schema')!r}"
        )
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        findings.append("questions must be a non-empty list")
        return findings
    seen_numbers: dict[str, int] = {}
    for index, question in enumerate(questions):
        label = f"question[{index}]"
        if not isinstance(question, dict):
            findings.append(f"{label} must be a JSON object")
            continue
        number = _question_number(question)
        if not number:
            findings.append(f"{label} is missing question_number")
        elif number in seen_numbers:
            findings.append(
                f"{label} duplicates question_number {number!r} "
                f"from question[{seen_numbers[number]}]"
            )
        else:
            seen_numbers[number] = index
        status = question.get("work_status")
        if status not in WORK_STATUSES:
            findings.append(
                f"{label} has unknown work_status {status!r}; "
                f"expected one of {', '.join(WORK_STATUSES)}"
            )
        for field in TEXT_FIELDS:
            if field not in question:
                findings.append(f"{label} is missing text field {field!r}")
            elif not isinstance(question[field], str):
                findings.append(
                    f"{label} field {field!r} must be a string, "
                    f"got {type(question[field]).__name__}"
                )
        if status == WORK_STATUS_TRANSCRIBED:
            for field in ("body", "answer"):
                if isinstance(question.get(field), str) and not question[field].strip():
                    findings.append(
                        f"{label} is transcribed but {field!r} is empty"
                    )
        if status == WORK_STATUS_NEEDS_REVIEW and not str(
            question.get("work_note") or ""
        ).strip():
            findings.append(
                f"{label} is needs_review but has no work_note explaining why"
            )
        for field in FORBIDDEN_WORKFILE_FIELDS:
            if field in question:
                findings.append(
                    f"{label} carries pipeline-owned field {field!r}; "
                    "the work file must not override it"
                )
    return findings


def transition_work_status(
    payload: dict, question_number: str, new_status: str
) -> dict:
    """Return a copy of the payload with one question's status advanced.

    Transitions are restricted to the transcription loop:
    ``pending -> transcribed``, ``pending -> needs_review``,
    ``transcribed -> needs_review``, and back from ``needs_review`` to
    ``transcribed``. Entering ``transcribed`` clears ``work_note`` because
    the doubt it described has been resolved.
    """
    if new_status not in WORK_STATUSES:
        raise ValueError(f"unknown work_status {new_status!r}")
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError("work file has no questions list")
    updated = dict(payload)
    new_questions = []
    found = False
    for question in questions:
        if isinstance(question, dict) and _question_number(question) == str(
            question_number
        ):
            found = True
            current = question.get("work_status")
            if current not in WORK_STATUSES:
                raise ValueError(
                    f"question {question_number!r} has unknown work_status "
                    f"{current!r}"
                )
            if current != new_status:
                if (current, new_status) not in _ALLOWED_TRANSITIONS:
                    raise ValueError(
                        f"transition {current!r} -> {new_status!r} is not "
                        "part of the transcription loop"
                    )
                revised = dict(question)
                revised["work_status"] = new_status
                if new_status == WORK_STATUS_TRANSCRIBED:
                    revised.pop("work_note", None)
                new_questions.append(revised)
                continue
        new_questions.append(question)
    if not found:
        raise KeyError(f"question_number {question_number!r} not found")
    updated["questions"] = new_questions
    return updated


def read_work_file(path: str | Path) -> dict:
    """Read a work file, tolerating a UTF-8 BOM added by editors."""
    with open(path, encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("work file must be a JSON object")
    return payload


def write_work_file(path: str | Path, payload: dict) -> None:
    """Publish the work file atomically (write to temp, then replace)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    with open(temp, "w", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temp, target)


__all__ = [
    "CODING_AGENT_WORKFILE_SCHEMA",
    "FORBIDDEN_WORKFILE_FIELDS",
    "TEXT_FIELDS",
    "WORK_STATUSES",
    "WORK_STATUS_NEEDS_REVIEW",
    "WORK_STATUS_PENDING",
    "WORK_STATUS_TRANSCRIBED",
    "read_work_file",
    "transition_work_status",
    "validate_work_file",
    "write_work_file",
]

