"""Read-only workspace health audit: report drift, never repair it.

A local-first workspace keeps canonical JSON question sets under
``<root>/question_sets/`` and asset files under an assets root. Edits made
outside the reviewed tools leave subtle inconsistency: an asset URI that
resolves to no file, an asset nobody references, or a SQLite row whose
derived columns drift from its payload. This module surfaces exactly that
drift as structured, serializable findings.

The read-only contract is absolute: the audit opens every file for
reading only, opens SQLite through a ``mode=ro`` URI so a missing table
is an error instead of a silent creation, and contains no repair path.
Fixing is always a separate, explicit, reviewed step. Part of #99.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Question, QuestionSet
from .storage import FilesystemStorageAdapter

WORKSPACE_AUDIT_VERSION = "workspace-audit/1"

CODE_UNREADABLE = "unreadable-set"
CODE_BROKEN_REFERENCE = "broken-reference"
CODE_ORPHAN_ASSET = "orphan-asset"
CODE_INDEX_DRIFT = "index-drift"

_ISSUE_FIELDS = {"code", "location", "detail"}
_REPORT_FIELDS = {
    "version",
    "sets_checked",
    "references_checked",
    "assets_checked",
    "rows_checked",
    "issues",
}


@dataclass(frozen=True, slots=True)
class AuditIssue:
    """One finding: a stable code, where, and why (no fix attached)."""

    code: str
    location: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "location": self.location, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditIssue:
        unknown = sorted(set(data) - _ISSUE_FIELDS)
        if unknown:
            raise ValueError(f"Unknown audit-issue field(s): {', '.join(unknown)}.")
        return cls(
            code=str(data["code"]),
            location=str(data["location"]),
            detail=str(data["detail"]),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceAuditReport:
    """Structured outcome of one audit run (pure data, no repairs)."""

    sets_checked: int
    references_checked: int
    assets_checked: int
    rows_checked: int
    issues: tuple[AuditIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": WORKSPACE_AUDIT_VERSION,
            "sets_checked": self.sets_checked,
            "references_checked": self.references_checked,
            "assets_checked": self.assets_checked,
            "rows_checked": self.rows_checked,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceAuditReport:
        unknown = sorted(set(data) - _REPORT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown audit-report field(s): {', '.join(unknown)}.")
        if str(data.get("version", WORKSPACE_AUDIT_VERSION)) != WORKSPACE_AUDIT_VERSION:
            raise ValueError(f"Unsupported audit version: {data['version']!r}.")
        return cls(
            sets_checked=int(data["sets_checked"]),
            references_checked=int(data["references_checked"]),
            assets_checked=int(data["assets_checked"]),
            rows_checked=int(data["rows_checked"]),
            issues=tuple(AuditIssue.from_dict(item) for item in data["issues"]),
        )


def _iter_questions(question_set: QuestionSet) -> Iterator[Question]:
    """Yield every question, walking subquestions depth-first."""
    stack = list(reversed(question_set.questions))
    while stack:
        question = stack.pop()
        stack.extend(reversed(question.subquestions))
        yield question


def _collect_assets(root: Path) -> tuple[list[tuple[QuestionSet, Question]], int, list[AuditIssue]]:
    """Load every stored set read-only; unreadable sets become issues."""
    storage = FilesystemStorageAdapter(root)
    questions: list[tuple[QuestionSet, Question]] = []
    issues: list[AuditIssue] = []
    sets_dir = root / "question_sets"
    for path in sorted(sets_dir.glob("*.json")) if sets_dir.is_dir() else []:
        try:
            question_set = storage.load(path.stem)
        except (OSError, TypeError, ValueError) as exc:
            issues.append(
                AuditIssue(CODE_UNREADABLE, path.name, str(exc))
            )
            continue
        questions.extend(
            (question_set, question) for question in _iter_questions(question_set)
        )
    return questions, len(issues), issues


def _audit_references(
    questions: list[tuple[QuestionSet, Question]], assets_root: Path
) -> tuple[int, set[Path], list[AuditIssue]]:
    """Check every file-URI asset for an on-disk target; track references."""
    issues: list[AuditIssue] = []
    referenced: set[Path] = set()
    checked = 0
    for question_set, question in questions:
        for asset in question.assets:
            if not _is_file_uri(asset.uri):
                continue
            checked += 1
            target = (assets_root / asset.uri).resolve()
            referenced.add(target)
            if not target.is_file():
                issues.append(
                    AuditIssue(
                        CODE_BROKEN_REFERENCE,
                        f"{question_set.id}/{question.id}/{asset.id}",
                        asset.uri,
                    )
                )
    return checked, referenced, issues


def _audit_orphans(
    referenced: set[Path], assets_root: Path
) -> tuple[int, list[AuditIssue]]:
    """Report asset files on disk that no question references."""
    if not assets_root.is_dir():
        return 0, []
    files = sorted(path for path in assets_root.rglob("*") if path.is_file())
    issues = [
        AuditIssue(
            CODE_ORPHAN_ASSET,
            path.resolve().relative_to(assets_root.resolve()).as_posix(),
            "no question references this asset",
        )
        for path in files
        if path.resolve() not in referenced
    ]
    return len(files), issues


def _audit_index(database: Path) -> tuple[int, list[AuditIssue]]:
    """Re-derive each SQLite row's columns from its payload, read-only."""
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            "SELECT id, payload, schema_version, question_count FROM question_sets"
        ).fetchall()
    finally:
        connection.close()
    issues: list[AuditIssue] = []
    for row_id, payload, schema_version, question_count in rows:
        try:
            question_set = QuestionSet.from_dict(json.loads(payload))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            issues.append(AuditIssue(CODE_INDEX_DRIFT, row_id, f"payload unreadable: {exc}"))
            continue
        if question_set.id != row_id:
            issues.append(
                AuditIssue(CODE_INDEX_DRIFT, row_id, f"payload declares id {question_set.id}")
            )
        if question_set.schema_version != schema_version:
            issues.append(
                AuditIssue(
                    CODE_INDEX_DRIFT,
                    row_id,
                    f"schema_version {schema_version} != {question_set.schema_version}",
                )
            )
        if len(question_set.questions) != question_count:
            issues.append(
                AuditIssue(
                    CODE_INDEX_DRIFT,
                    row_id,
                    f"question_count {question_count} != {len(question_set.questions)}",
                )
            )
    return len(rows), issues


def audit_workspace(
    root: Path,
    assets_root: Path | None = None,
    database: Path | None = None,
) -> WorkspaceAuditReport:
    """Run every read-only health check over one workspace (never mutates).

    Checks: unreadable stored sets, broken asset references, orphan asset
    files, and - when a database path is given - SQLite derived-column
    drift, opened strictly read-only. The report is pure data; repairing
    anything is always a separate, explicit step.
    """
    root = Path(root)
    assets = assets_root if assets_root is not None else root / "assets"
    questions, _, issues = _collect_assets(root)
    sets_checked = len({question_set.id for question_set, _ in questions})
    references_checked, referenced, reference_issues = _audit_references(questions, assets)
    assets_checked, orphan_issues = _audit_orphans(referenced, assets)
    rows_checked, drift_issues = _audit_index(database) if database is not None else (0, [])
    return WorkspaceAuditReport(
        sets_checked=sets_checked,
        references_checked=references_checked,
        assets_checked=assets_checked,
        rows_checked=rows_checked,
        issues=tuple(issues + reference_issues + orphan_issues + drift_issues),
    )



def _is_file_uri(uri: str) -> bool:
    """Relative-path URIs are files; HTTPS and data: URIs are not."""
    return "://" not in uri and not uri.startswith("data:")
