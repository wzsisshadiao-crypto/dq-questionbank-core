"""Read-only postflight checks for staged question candidates.

After a coding agent finishes a work file and the deterministic finalize
stage has run, questions are staged as one ``qNN.json`` file each. The
postflight scan is the last gate before registration: it verifies that the
staged directory is complete, continuous, and internally consistent using
nothing but the files themselves.

The scanner deliberately depends only on files supplied by the caller. It
does not import the application, open a database, inspect PDF evidence, or
invoke an AI service::

    report = scan_candidate_dir(staging_dir)
    if not report["ok"]:
        print("\\n".join(report["findings"]))
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

POSTFLIGHT_REPORT_SCHEMA = "pdf-postflight-report/v1"

MANIFEST_NAME = "manifest.json"
REQUIRED_QUESTION_FIELDS = ("question_number", "question_id", "source")

QUESTION_FILE_RE = re.compile(r"^q(?P<number>\d{2,})\.json$", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_question_sha256(payload: dict) -> str:
    """Stable content hash: sorted keys, no whitespace, UTF-8 bytes."""
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> object:
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def scan_candidate_dir(root: str | Path) -> dict:
    """Scan a staged candidate directory and return a report dictionary.

    The directory contract is: one ``qNN.json`` file per question (numbers
    continuous from 1, no duplicates), plus an optional ``manifest.json``
    mapping file names to SHA-256 digests. Anything else is a finding, and
    a staged question may carry its own ``content_sha256`` which must match
    the canonical hash of its content.
    """
    directory = Path(root)
    findings: list[str] = []
    if not directory.is_dir():
        return {
            "schema": POSTFLIGHT_REPORT_SCHEMA,
            "root": str(directory),
            "ok": False,
            "question_count": 0,
            "questions": [],
            "findings": [f"staging directory does not exist: {directory}"],
        }

    staged: dict[int, Path] = {}
    manifest_path: Path | None = None
    for entry in sorted(directory.iterdir()):
        if not entry.is_file():
            findings.append(f"unexpected non-file entry: {entry.name}")
            continue
        match = QUESTION_FILE_RE.match(entry.name)
        if match:
            number = int(match.group("number"))
            if number in staged:
                findings.append(
                    f"duplicate question number {number}: "
                    f"{staged[number].name} and {entry.name}"
                )
            else:
                staged[number] = entry
            continue
        if entry.name == MANIFEST_NAME:
            manifest_path = entry
            continue
        findings.append(f"unexpected file in staging directory: {entry.name}")

    numbers = sorted(staged)
    if numbers:
        if numbers[0] != 1:
            findings.append(
                f"question numbering starts at {numbers[0]}, expected 1"
            )
        missing = sorted(
            number for number in range(1, numbers[-1] + 1)
            if number not in staged
        )
        if missing:
            findings.append(
                "question numbering has gaps: "
                + ", ".join(f"q{number:02d}" for number in missing)
            )

    questions: list[dict] = []
    hashes: dict[str, str] = {}
    for number in numbers:
        path = staged[number]
        label = path.name
        try:
            payload = _read_json(path)
        except (OSError, json.JSONDecodeError) as error:
            findings.append(f"{label} is not readable JSON: {error}")
            continue
        if not isinstance(payload, dict):
            findings.append(f"{label} must contain a JSON object")
            continue
        record = {
            "file": label,
            "number": number,
            "sha256": canonical_question_sha256(payload),
        }
        hashes[label] = record["sha256"]
        for field in REQUIRED_QUESTION_FIELDS:
            value = payload.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                findings.append(f"{label} is missing {field}")
            else:
                record[field] = value
        declared = payload.get("content_sha256")
        if declared is not None:
            if not isinstance(declared, str) or not SHA256_RE.match(declared):
                findings.append(
                    f"{label} carries a malformed content_sha256: {declared!r}"
                )
            elif declared != record["sha256"]:
                findings.append(
                    f"{label} content_sha256 does not match its content "
                    f"(declared {declared}, computed {record['sha256']})"
                )
        questions.append(record)

    if manifest_path is not None:
        try:
            manifest = _read_json(manifest_path)
        except (OSError, json.JSONDecodeError) as error:
            findings.append(f"{MANIFEST_NAME} is not readable JSON: {error}")
            manifest = None
        if isinstance(manifest, dict):
            entries = manifest.get("files", manifest)
            if not isinstance(entries, dict):
                findings.append(
                    f"{MANIFEST_NAME} must map file names to SHA-256 digests"
                )
            else:
                for name in sorted(set(entries) - set(hashes)):
                    findings.append(
                        f"{MANIFEST_NAME} lists unknown file {name}"
                    )
                for name in sorted(set(hashes) & set(entries)):
                    if entries[name] != hashes[name]:
                        findings.append(
                            f"{MANIFEST_NAME} digest mismatch for {name}: "
                            f"listed {entries[name]}, computed {hashes[name]}"
                        )
        elif manifest is not None:
            findings.append(f"{MANIFEST_NAME} must contain a JSON object")

    return {
        "schema": POSTFLIGHT_REPORT_SCHEMA,
        "root": str(directory),
        "ok": not findings,
        "question_count": len(questions),
        "questions": questions,
        "findings": findings,
    }


__all__ = [
    "MANIFEST_NAME",
    "POSTFLIGHT_REPORT_SCHEMA",
    "QUESTION_FILE_RE",
    "REQUIRED_QUESTION_FIELDS",
    "canonical_question_sha256",
    "scan_candidate_dir",
]

