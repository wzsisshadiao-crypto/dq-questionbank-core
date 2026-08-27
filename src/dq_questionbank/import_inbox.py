"""The AI-import inbox contract (``ai-inbox-batch/v1``).

This is the human-verification gate between a finished AI/coding-agent
import and the question bank: channels **deliver** a batch directory,
the inbox **registers** it after verification, humans **review** it, and
only an explicit confirmation with a matching cryptographic anchor may
**transfer** the batch into storage.

Directory shape::

    inbox/<batch_id>/
      batch.json          # schema ai-inbox-batch/v1 (this contract)
      questions/qNN.json  # one file per question
      evidence/           # read-only extraction/OCR evidence (optional)

Design rules distilled from the production inbox:

- the manifest digest is **computed by the receiver** from the question
  files - a digest declared by the delivering channel is never trusted;
- batches with unresolved blocking findings stay ``blocked`` and cannot
  proceed to review or transfer;
- registration returns a ``confirmation_digest`` anchored to
  ``batch_id + manifest``; :func:`verify_receipt` recomputes both later and
  detects any post-registration edit (tamper or drift) before transfer;
- this module is pure: it touches only the paths the caller provides.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .exceptions import QuestionBankError
from .pdf_postflight import (
    QUESTION_FILE_RE,
    canonical_question_sha256,
)

IMPORT_INBOX_SCHEMA = "ai-inbox-batch/v1"

BATCH_STATUS_REGISTERED = "registered"
BATCH_STATUS_BLOCKED = "blocked"
#: Terminal batch states - no longer participants in in-flight checks.
BATCH_TERMINAL_STATUSES = ("transferred", "rejected", "archived", "purged")

#: Per-question human review verdicts recorded on the batch record.
QUESTION_VERDICTS = ("passed", "fixed", "rejected")

REQUIRED_BATCH_FIELDS = ("batch_id", "source", "questions")
BATCH_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,96}$")


class ImportInboxError(QuestionBankError):
    """An inbox operation failed with a stable error code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _read_json(path: Path) -> object:
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def batch_manifest_digest(questions_dir: str | Path) -> str:
    """Receiver-computed SHA-256 over the canonical question file hashes.

    Files are visited in sorted ``qNN`` order; every file contributes
    ``"<name>:<canonical question sha256>\\n"``. A single changed byte in
    any question therefore changes the manifest digest.
    """
    directory = Path(questions_dir)
    entries = []
    for path in sorted(directory.iterdir()) if directory.is_dir() else []:
        match = QUESTION_FILE_RE.match(path.name)
        if match and path.is_file():
            try:
                payload = _read_json(path)
            except (OSError, json.JSONDecodeError) as error:
                raise ImportInboxError(
                    "question-file-unreadable", f"{path.name}: {error}"
                ) from error
            if not isinstance(payload, dict):
                raise ImportInboxError(
                    "question-file-not-object", path.name
                )
            entries.append(
                f"{path.name}:{canonical_question_sha256(payload)}\n"
            )
    if not entries:
        raise ImportInboxError("empty-questions-dir", str(directory))
    return hashlib.sha256("".join(entries).encode("utf-8")).hexdigest()


def validate_batch(batch: object) -> list[str]:
    """Return human-readable contract violations (empty list when valid)."""
    findings: list[str] = []
    if not isinstance(batch, dict):
        return ["batch must be a JSON object"]
    if batch.get("schema") != IMPORT_INBOX_SCHEMA:
        findings.append(
            f"schema must be {IMPORT_INBOX_SCHEMA!r}, got {batch.get('schema')!r}"
        )
    batch_id = batch.get("batch_id")
    if not isinstance(batch_id, str) or not BATCH_ID_RE.match(batch_id):
        findings.append(
            "batch_id is required and must match [A-Za-z0-9_-]{1,96}"
        )
    if not str(batch.get("source") or "").strip():
        findings.append("source is required (which paper/channel delivered this)")
    questions = batch.get("questions")
    if not isinstance(questions, list) or not questions:
        findings.append("questions must be a non-empty list of file entries")
        return findings
    seen: set[str] = set()
    for index, entry in enumerate(questions):
        label = f"questions[{index}]"
        if not isinstance(entry, dict) or not str(entry.get("file") or "").strip():
            findings.append(f"{label} must carry a 'file' name")
            continue
        name = str(entry["file"])
        if not QUESTION_FILE_RE.match(name):
            findings.append(f"{label} file name must match qNN.json: {name!r}")
        if name in seen:
            findings.append(f"{label} duplicates file {name!r}")
        seen.add(name)
    verdicts = batch.get("verdicts")
    if verdicts is not None:
        if not isinstance(verdicts, dict):
            findings.append("verdicts must map question files to review verdicts")
        else:
            for name, verdict in sorted(verdicts.items()):
                if verdict not in QUESTION_VERDICTS:
                    findings.append(
                        f"verdicts[{name!r}] must be one of "
                        f"{', '.join(QUESTION_VERDICTS)}; got {verdict!r}"
                    )
            unknown = sorted(set(verdicts) - seen)
            for name in unknown:
                findings.append(f"verdicts references unknown file {name!r}")
    return findings


def register_batch(
    batch: object, questions_dir: str | Path
) -> dict:
    """Validate + anchor a delivered batch; never raises for content issues.

    Returns a registration record. Blocking findings leave the batch in
    ``blocked``; otherwise the record carries the receiver-computed
    ``manifest_sha256`` and a ``confirmation_digest`` that
    :func:`verify_receipt` must match before any transfer into storage.
    """
    findings = validate_batch(batch)
    question_count = 0
    manifest = ""
    directory = Path(questions_dir)
    declared = (
        {
            str(entry["file"])
            for entry in (batch.get("questions") or [])
            if isinstance(entry, dict) and str(entry.get("file") or "").strip()
        }
        if isinstance(batch, dict)
        else set()
    )
    if directory.is_dir():
        present = {
            path.name for path in directory.iterdir()
            if path.is_file() and QUESTION_FILE_RE.match(path.name)
        }
        question_count = len(present)
        for name in sorted(declared - present):
            findings.append(f"declared question file missing on disk: {name}")
        for name in sorted(present - declared):
            findings.append(f"undeclared question file in delivery: {name}")
        if present:
            try:
                manifest = batch_manifest_digest(directory)
            except ImportInboxError as error:
                findings.append(f"{error.code}: {error.detail}")
    else:
        findings.append(f"questions directory does not exist: {directory}")

    batch_id = str(batch.get("batch_id") or "") if isinstance(batch, dict) else ""
    confirmation = ""
    if manifest and not findings:
        confirmation = hashlib.sha256(
            f"{batch_id}:{manifest}".encode()
        ).hexdigest()
    return {
        "schema": IMPORT_INBOX_SCHEMA,
        "batch_id": batch_id,
        "status": BATCH_STATUS_BLOCKED if findings else BATCH_STATUS_REGISTERED,
        "question_count": question_count,
        "manifest_sha256": manifest,
        "confirmation_digest": confirmation,
        "findings": findings,
    }


def verify_receipt(record: dict, questions_dir: str | Path) -> dict:
    """Recompute the anchor before transfer; detects post-registration edits."""
    if record.get("status") != BATCH_STATUS_REGISTERED:
        raise ImportInboxError(
            "batch-not-registered",
            f"status is {record.get('status')!r}, "
            "only registered batches can be verified for transfer",
        )
    current = batch_manifest_digest(questions_dir)
    expected = record.get("manifest_sha256")
    ok = bool(expected) and current == expected
    confirmation = hashlib.sha256(
        f"{record.get('batch_id', '')}:{current}".encode()
    ).hexdigest()
    return {
        "verified": ok,
        "manifest_sha256": current,
        "confirmation_digest": confirmation if ok else "",
        "reason": "" if ok else "questions changed after registration",
    }


__all__ = [
    "BATCH_STATUS_BLOCKED",
    "BATCH_STATUS_REGISTERED",
    "BATCH_TERMINAL_STATUSES",
    "IMPORT_INBOX_SCHEMA",
    "ImportInboxError",
    "QUESTION_VERDICTS",
    "REQUIRED_BATCH_FIELDS",
    "batch_manifest_digest",
    "register_batch",
    "validate_batch",
    "verify_receipt",
]


