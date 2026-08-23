"""Batch acceptance reports over reviewed import sessions.

After every candidate in an import session carries an explicit review
decision, reviewers need one deterministic summary — which rules fired,
how often, with what outcomes — instead of re-reading each candidate by
hand. :func:`build_acceptance_report` aggregates a reviewed session into
plain counts keyed by the existing public rule identities (the
``code`` vocabulary candidates already carry in their diagnostics; no new
id scheme), plus the decision totals.

The report is a pure function of the session document: no file or
network I/O, no timestamps, no randomness. Serialization follows the
repo style (``to_dict`` / ``from_dict`` with unknown-key rejection) and
:func:`render_markdown_table` produces a short, stable Markdown table.

Clean-room implementation from synthetic fixtures; part of issue #84.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .intake import _verify_session
from .review_session import DECISION_ACCEPTED, DECISION_PENDING, DECISION_REJECTED

ACCEPTANCE_REPORT_VERSION = "acceptance-report/1"

_REPORT_FIELDS = {
    "report_version",
    "route",
    "bundle_id",
    "totals",
    "candidates",
    "edited_candidates",
    "rule_counts",
    "applied_proposal_changes",
}


@dataclass(frozen=True, slots=True)
class AcceptanceReport:
    """One deterministic per-rule summary of a reviewed import session."""

    route: str
    bundle_id: str
    totals: tuple[tuple[str, int], ...]
    candidates: int
    edited_candidates: int
    rule_counts: tuple[tuple[str, int], ...]
    applied_proposal_changes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_version": ACCEPTANCE_REPORT_VERSION,
            "route": self.route,
            "bundle_id": self.bundle_id,
            "totals": dict(self.totals),
            "candidates": self.candidates,
            "edited_candidates": self.edited_candidates,
            "rule_counts": dict(self.rule_counts),
            "applied_proposal_changes": self.applied_proposal_changes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcceptanceReport:
        unknown = sorted(set(data) - _REPORT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown acceptance-report field(s): {', '.join(unknown)}.")
        if data.get("report_version") != ACCEPTANCE_REPORT_VERSION:
            raise ValueError(f"Unsupported report version: {data.get('report_version')!r}")
        totals = data["totals"]
        rule_counts = data["rule_counts"]
        return cls(
            route=str(data["route"]),
            bundle_id=str(data["bundle_id"]),
            totals=tuple(sorted((str(key), int(value)) for key, value in totals.items())),
            candidates=int(data["candidates"]),
            edited_candidates=int(data["edited_candidates"]),
            rule_counts=tuple(
                sorted((str(key), int(value)) for key, value in rule_counts.items())
            ),
            applied_proposal_changes=int(data["applied_proposal_changes"]),
        )


def build_acceptance_report(session: dict[str, Any]) -> AcceptanceReport:
    """Aggregate one reviewed import session into per-rule counts (pure)."""
    verified = _verify_session(session)
    candidates = verified.get("candidates") or []
    totals_map: dict[str, int] = {
        DECISION_ACCEPTED: 0,
        DECISION_REJECTED: 0,
        DECISION_PENDING: 0,
    }
    rule_map: dict[str, int] = {}
    edited = 0
    for candidate in candidates:
        decision = str(candidate.get("decision", DECISION_PENDING))
        if decision in totals_map:
            totals_map[decision] += 1
        if int(candidate.get("revision", 1)) > 1:
            edited += 1
        for diagnostic in candidate.get("diagnostics") or []:
            rule_id = diagnostic.get("code") if isinstance(diagnostic, dict) else None
            if isinstance(rule_id, str) and rule_id:
                rule_map[rule_id] = rule_map.get(rule_id, 0) + 1
    proposal = verified.get("proposal") or {}
    applied = proposal.get("changes") or [] if proposal.get("applied") else []
    return AcceptanceReport(
        route=str(verified.get("route", "")),
        bundle_id=str(verified.get("bundle_id", "")),
        totals=tuple(sorted(totals_map.items())),
        candidates=len(candidates),
        edited_candidates=edited,
        rule_counts=tuple(sorted(rule_map.items())),
        applied_proposal_changes=len(applied),
    )


def render_markdown_table(report: AcceptanceReport) -> str:
    """Render the report as a short, deterministic Markdown table."""
    lines = [
        f"# Acceptance report — {report.bundle_id} ({report.route})",
        "",
        f"- Candidates: {report.candidates} "
        f"(accepted {dict(report.totals).get(DECISION_ACCEPTED, 0)}, "
        f"rejected {dict(report.totals).get(DECISION_REJECTED, 0)}, "
        f"pending {dict(report.totals).get(DECISION_PENDING, 0)}; "
        f"edited {report.edited_candidates})",
        f"- Applied proposal changes: {report.applied_proposal_changes}",
        "",
        "| Rule | Count |",
        "|---|---|",
    ]
    for rule_id, count in report.rule_counts:
        lines.append(f"| {rule_id} | {count} |")
    if not report.rule_counts:
        lines.append("| (no rules fired) | 0 |")
    return "\n".join(lines) + "\n"
