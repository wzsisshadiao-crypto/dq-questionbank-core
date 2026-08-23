"""Fail-closed safety gate for reviewed candidate edits.

Every reviewed edit that replaces a candidate payload must pass this gate
before it is applied. The gate is a pure decision function — no I/O, no
mutation, no globals — and it fail-closes: an edit is allowed only when it
proves it is safe.

The three rules (evaluated in order, first violation wins):

1. **Field allowlist** — only pre-declared question fields may change.
   Ids, question type, language, schema version, provenance (``source``),
   taxonomy, and assets are protected: an edit never rewrites who a
   question is or where it came from.
2. **Proven progress** — when the original carries open quality findings,
   the edit must resolve at least one of them (its rule/field identity no
   longer fires), or the reviewer must attach an explicit progress
   declaration naming why not. An edit on a candidate with no open
   findings has nothing to prove; the digest and revision machinery
   already record it.
3. **No new errors** — the edited question must not introduce new
   semantic validation errors or new quality findings that the original
   did not carry.

Denials are machine-readable: one canonical reason plus deterministic
``key=value`` evidence strings, mirroring :mod:`dq_questionbank.import_triage`.

Clean-room implementation from synthetic fixtures; part of issue #85.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .models import Question
from .quality_findings import QualityFinding, detect_quality_findings
from .validation import validate_question

SAFE_REPAIR_VERSION = "safe-repair/1"

GATE_ALLOW = "allow"
GATE_DENY = "deny"
GATE_DECISIONS = (GATE_ALLOW, GATE_DENY)

REASON_MALFORMED = "malformed-edit"
REASON_ALLOWLIST = "field-allowlist-violation"
REASON_NO_PROGRESS = "no-proven-progress"
REASON_NEW_VALIDATION_ERRORS = "new-validation-errors"
REASON_NEW_QUALITY_FINDINGS = "new-quality-findings"

# Fields a reviewed edit may rewrite. Everything else — id, type, language,
# schema_version, source, taxonomy, assets — is identity or provenance and
# is protected by rule 1.
EDITABLE_FIELDS = frozenset(
    {
        "stem",
        "choices",
        "answer",
        "solution",
        "analysis",
        "hints",
        "tags",
        "difficulty",
        "metadata",
        "subject",
        "subquestions",
    }
)

_GATE_FIELDS = {"decision", "reasons", "evidence"}


def changed_fields(original: Question, edited: Question) -> tuple[str, ...]:
    """Return the sorted top-level fields whose payloads differ.

    Comparison uses each question's canonical ``to_dict`` serialization,
    so only content that survives the documented wire format counts as a
    change.
    """
    before = original.to_dict()
    after = edited.to_dict()
    keys = set(before) | set(after)
    return tuple(sorted(key for key in keys if before.get(key) != after.get(key)))


def _finding_identities(findings: Sequence[QualityFinding]) -> set[tuple[str, str]]:
    """Map findings to their ``(rule_id, target_field)`` identities."""
    return {(str(finding.rule_id), str(finding.target_field)) for finding in findings}


def _validation_errors(question: Question) -> set[tuple[str, str]]:
    """Map error-severity validation issues to ``(path, message)`` pairs."""
    return {
        (str(issue.path), str(issue.message))
        for issue in validate_question(question)
        if issue.severity == "error"
    }

@dataclass(frozen=True, slots=True)
class GateDecision:
    """One deterministic gate decision over a reviewed edit.

    ``reasons`` names the rule that denied the edit (exactly one canonical
    reason per denial) and ``evidence`` carries deterministic ``key=value``
    strings such as ``changed-fields=stem`` or ``resolved-findings=1`` so a
    reviewer can audit the denial without re-running detection. No
    timestamp or provenance is stored: determinism comes first.
    """

    decision: str
    reasons: tuple[str, ...]
    evidence: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return self.decision == GATE_ALLOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GateDecision:
        unknown = sorted(set(data) - _GATE_FIELDS)
        if unknown:
            raise ValueError(f"Unknown gate-decision field(s): {', '.join(unknown)}.")
        decision = str(data["decision"])
        if decision not in GATE_DECISIONS:
            raise ValueError(f"Unsupported decision: {decision!r}")
        return cls(
            decision=decision,
            reasons=tuple(str(item) for item in data["reasons"]),
            evidence=tuple(str(item) for item in data["evidence"]),
        )


def _deny(reason: str, evidence: tuple[str, ...]) -> GateDecision:
    return GateDecision(decision=GATE_DENY, reasons=(reason,), evidence=evidence)


def _allow(evidence: tuple[str, ...]) -> GateDecision:
    return GateDecision(decision=GATE_ALLOW, reasons=(), evidence=evidence)


def evaluate_repair(
    original: Question,
    edited: Question,
    findings: Sequence[QualityFinding] = (),
    *,
    progress_declaration: str | None = None,
) -> GateDecision:
    """Decide whether one reviewed edit may replace its candidate.

    ``findings`` are the open quality findings the reviewer acted on (in
    the review pipeline these come from
    :func:`dq_questionbank.detect_quality_findings` over the original
    payload). ``progress_declaration`` is the reviewer's explicit, non-
    empty explanation for an edit that resolves no finding (for example a
    pure wording change on a candidate that does carry findings).
    """
    if not isinstance(original, Question) or not isinstance(edited, Question):
        return _deny(
            REASON_MALFORMED,
            (
                f"original-type={type(original).__name__}",
                f"edited-type={type(edited).__name__}",
            ),
        )

    changed = changed_fields(original, edited)
    changed_evidence = (f"changed-fields={','.join(changed) if changed else 'none'}",)

    violations = [field for field in changed if field not in EDITABLE_FIELDS]
    if violations:
        return _deny(
            REASON_ALLOWLIST,
            changed_evidence + (f"violations={','.join(sorted(violations))}",),
        )

    open_findings = tuple(findings)
    edited_identities = _finding_identities(detect_quality_findings(edited))
    resolved = [
        finding
        for finding in open_findings
        if (str(finding.rule_id), str(finding.target_field)) not in edited_identities
    ]
    declared = isinstance(progress_declaration, str) and bool(progress_declaration.strip())
    if open_findings and not resolved and not declared:
        return _deny(
            REASON_NO_PROGRESS,
            changed_evidence
            + (
                f"open-findings={len(open_findings)}",
                f"resolved-findings={len(resolved)}",
                "progress-declaration=missing",
            ),
        )

    new_errors = _validation_errors(edited) - _validation_errors(original)
    if new_errors:
        return _deny(
            REASON_NEW_VALIDATION_ERRORS,
            changed_evidence + (f"new-validation-errors={len(new_errors)}",),
        )

    new_findings = edited_identities - _finding_identities(open_findings)
    if new_findings:
        return _deny(
            REASON_NEW_QUALITY_FINDINGS,
            changed_evidence + (f"new-quality-findings={len(new_findings)}",),
        )

    return _allow(
        changed_evidence
        + (
            f"open-findings={len(open_findings)}",
            f"resolved-findings={len(resolved)}",
            f"new-quality-findings={len(new_findings)}",
        )
        + (("progress-declaration=declared",) if declared else ())
    )

