"""Deterministic triage decisions for imported question candidates.

This module grades one extracted candidate into a routing decision —
``patch``, ``full_redo``, or ``needs_human`` — as a pure decision
function: no I/O, no globals, no timestamps, and no randomness, so the
same candidate dict always produces the same decision.

The grading is conservative and first-match-wins:

1. a missing or non-dict ``question`` payload is ``malformed-candidate``;
2. a candidate with no findings at all is a ``no-findings`` patch;
3. at most two error findings, all scoped to a single field family
   (for example every finding targets ``stem.blocks[...]`` only), is a
   ``bounded-single-field-findings`` patch;
4. more than two error findings, or error findings spanning several
   field families (stem and solution, or choices), is a
   ``widespread-findings`` full redo;
5. anything the contract cannot decide — an empty question payload, a
   ``findings`` entry with an unsupported shape or severity, an error
   finding without a usable field path, warning/info-only findings, or a
   missing ``findings`` key while diagnostics are present — fails closed
   to ``needs_human`` as ``ambiguous-candidate``.

Clean-room implementation from synthetic fixtures; part of issue #86.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

TRIAGE_VERSION = "triage/1"

DECISION_PATCH = "patch"
DECISION_FULL_REDO = "full_redo"
DECISION_NEEDS_HUMAN = "needs_human"
DECISIONS = (DECISION_PATCH, DECISION_FULL_REDO, DECISION_NEEDS_HUMAN)

REASON_MALFORMED = "malformed-candidate"
REASON_NO_FINDINGS = "no-findings"
REASON_BOUNDED = "bounded-single-field-findings"
REASON_WIDESPREAD = "widespread-findings"
REASON_AMBIGUOUS = "ambiguous-candidate"

ERROR_SEVERITY = "error"
WARNING_SEVERITY = "warning"
INFO_SEVERITY = "info"
SEVERITIES = (ERROR_SEVERITY, WARNING_SEVERITY, INFO_SEVERITY)

# An error finding is only patchable while the whole repair stays inside
# one field family; two is the largest bounded set the contract allows.
MAX_PATCHABLE_ERRORS = 2

_DECISION_FIELDS = {"decision", "reasons", "evidence"}

_BLOCK_PATH_RE = re.compile(r"^(stem|solution)\.blocks\[\d+\]$")
_CHOICE_PATH_RE = re.compile(r"^choices\[\d+\]\.content$")
_TOP_LEVEL_PATHS = ("stem", "answer", "solution", "choices", "metadata")

_DIAGNOSTIC_KEYS = ("diagnostics",)


def _field_scope(target_field: Any) -> str | None:
    """Map a finding's target path to its field-family scope.

    Returns ``"<field>.blocks"`` for stem/solution block paths,
    ``"choices"`` for choice-content paths, the field name itself for
    supported top-level paths, and ``None`` when the path is missing or
    outside the supported finding vocabulary — callers treat that as
    ambiguity instead of guessing a scope.
    """
    if not isinstance(target_field, str):
        return None
    block_match = _BLOCK_PATH_RE.match(target_field)
    if block_match:
        return f"{block_match.group(1)}.blocks"
    if _CHOICE_PATH_RE.match(target_field):
        return "choices"
    if target_field in _TOP_LEVEL_PATHS:
        return target_field
    return None


@dataclass(frozen=True, slots=True)
class TriageDecision:
    """One deterministic triage decision over an import candidate.

    ``reasons`` names the rule that fired (exactly one canonical reason
    per decision) and ``evidence`` carries deterministic ``key=value``
    strings such as ``error-findings=2`` or ``fields=stem.blocks`` so a
    reviewer can audit the routing without re-running detection. No
    timestamp or provenance is stored: determinism of fixtures comes
    first, and callers can add their own envelopes.
    """

    decision: str
    reasons: tuple[str, ...]
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TriageDecision:
        unknown = sorted(set(data) - _DECISION_FIELDS)
        if unknown:
            raise ValueError(f"Unknown triage-decision field(s): {', '.join(unknown)}.")
        decision = str(data["decision"])
        if decision not in DECISIONS:
            raise ValueError(f"Unsupported decision: {decision!r}")
        return cls(
            decision=decision,
            reasons=tuple(str(item) for item in data["reasons"]),
            evidence=tuple(str(item) for item in data["evidence"]),
        )


def _decide(decision: str, reason: str, evidence: tuple[str, ...]) -> TriageDecision:
    """Build a single-reason decision (one canonical reason per rule)."""
    return TriageDecision(decision=decision, reasons=(reason,), evidence=evidence)


def _needs_human(reason: str, evidence: tuple[str, ...]) -> TriageDecision:
    """Build the fail-closed ``needs_human`` outcome."""
    return _decide(DECISION_NEEDS_HUMAN, reason, evidence)


def triage_candidate(candidate: dict[str, Any]) -> TriageDecision:
    """Grade one import candidate into a routing decision (pure function).

    The candidate is a plain dict: ``question`` (the extracted question
    payload), an optional ``findings`` list of finding dicts (each may
    carry ``rule_id``, ``severity``, and ``target_field``), and an
    optional ``route`` string that is recorded as evidence only and
    never changes the decision. Rules are evaluated in the documented
    order and the first match wins; anything the contract cannot decide
    fails closed to ``needs_human``.
    """
    if not isinstance(candidate, dict):
        return _needs_human(
            REASON_MALFORMED, (f"candidate-type={type(candidate).__name__}",)
        )

    question = candidate.get("question")
    if not isinstance(question, dict):
        evidence = (
            ("question=missing",)
            if question is None
            else (f"question-type={type(question).__name__}",)
        )
        return _needs_human(REASON_MALFORMED, evidence)

    route = candidate.get("route")
    route_evidence = (f"route={route}",) if isinstance(route, str) and route else ()

    if not question:
        return _needs_human(REASON_AMBIGUOUS, ("question=empty",) + route_evidence)

    if "findings" not in candidate:
        if any(candidate.get(key) for key in _DIAGNOSTIC_KEYS):
            return _needs_human(
                REASON_AMBIGUOUS, ("findings=missing", "diagnostics=present")
            )
        raw_findings: list[Any] = []
    else:
        raw_findings = candidate["findings"]
        if not isinstance(raw_findings, list):
            return _needs_human(
                REASON_AMBIGUOUS,
                (f"findings-type={type(raw_findings).__name__}",) + route_evidence,
            )

    if not raw_findings:
        return _decide(
            DECISION_PATCH,
            REASON_NO_FINDINGS,
            ("total-findings=0", "error-findings=0") + route_evidence,
        )

    errors = 0
    warnings = 0
    infos = 0
    unscoped_errors = 0
    unsupported_severities = 0
    scopes: list[str] = []
    for finding in raw_findings:
        if not isinstance(finding, dict):
            return _needs_human(
                REASON_AMBIGUOUS,
                (f"finding-type={type(finding).__name__}",) + route_evidence,
            )
        severity = finding.get("severity")
        if severity == ERROR_SEVERITY:
            scope = _field_scope(finding.get("target_field"))
            if scope is None:
                unscoped_errors += 1
            else:
                scopes.append(scope)
                errors += 1
        elif severity == WARNING_SEVERITY:
            warnings += 1
        elif severity == INFO_SEVERITY:
            infos += 1
        else:
            unsupported_severities += 1

    counts = (
        f"total-findings={len(raw_findings)}",
        f"error-findings={errors}",
        f"warning-findings={warnings}",
        f"info-findings={infos}",
    )
    if unsupported_severities:
        return _needs_human(
            REASON_AMBIGUOUS,
            (f"unsupported-severity-findings={unsupported_severities}",)
            + route_evidence,
        )
    if unscoped_errors:
        return _needs_human(
            REASON_AMBIGUOUS,
            (f"unscoped-error-findings={unscoped_errors}",) + route_evidence,
        )
    if errors == 0:
        # Warning/info findings alone authorize neither a mechanical patch
        # nor a redo; the contract fails closed to human review.
        return _needs_human(REASON_AMBIGUOUS, counts + route_evidence)

    fields_evidence = (f"fields={','.join(sorted(set(scopes)))}",)
    if errors <= MAX_PATCHABLE_ERRORS and len(set(scopes)) == 1:
        return _decide(
            DECISION_PATCH,
            REASON_BOUNDED,
            counts + fields_evidence + route_evidence,
        )
    return _decide(
        DECISION_FULL_REDO,
        REASON_WIDESPREAD,
        counts + fields_evidence + route_evidence,
    )
