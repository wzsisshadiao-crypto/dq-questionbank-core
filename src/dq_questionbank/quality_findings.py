"""Revision-bound quality findings for the public Quality Center.

This module defines the minimal public contract for quality findings:

- a finding is bound to a question id, a target field, a rule id, the
  ruleset version, and deterministic fingerprints over the fields the rule
  actually read (its input dependencies);
- human judgment (accept or reject) is a separate operation that fails
  closed with :class:`StaleFindingError` when any declared dependency no
  longer matches its fingerprint;
- preview-only repair data may ride along, but nothing here rewrites a
  question.

Detection, judgment, and persistence stay separate: ``detect_quality_findings``
produces findings from the deterministic LaTeX rules, ``judge_finding``
records a human decision, and ``to_dict``/``from_dict`` provide the stable
serialized form used by fixtures and callers.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .exceptions import StaleFindingError
from .latex_repair import repair_latex_source
from .models import Content, Question

RULESET_VERSION = "quality/1"
SEVERITIES = ("error", "warning", "info")
DECISIONS = ("accepted", "rejected")
STATE_CURRENT = "current"
STATE_STALE = "stale"

_FINDING_FIELDS = {
    "question_id",
    "target_field",
    "rule_id",
    "ruleset_version",
    "input_fingerprints",
    "severity",
    "explanation",
    "repair",
}
_JUDGMENT_FIELDS = {"decision", "finding", "finding_fingerprint"}

_BLOCK_PATH_RE = re.compile(r"^(stem|solution)\.blocks\[(\d+)\]$")
_CHOICE_PATH_RE = re.compile(r"^choices\[(\d+)\]\.content$")
_TOP_LEVEL_PATHS = ("stem", "answer", "solution", "choices", "metadata")


def field_fingerprint(value: Any) -> str:
    """Return the deterministic fingerprint of one field value.

    The fingerprint is the SHA-256 digest of the canonical JSON form:
    sorted keys, compact separators, no ASCII escaping. Mapping key order
    therefore never changes a fingerprint, while any content change does.
    """
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_field_path(question: Question, path: str) -> Any:
    """Resolve a supported field path to its current serializable value."""
    if path in _TOP_LEVEL_PATHS:
        value = getattr(question, path, None)
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if path == "choices":
            return [choice.to_dict() for choice in value or []]
        return value
    block_match = _BLOCK_PATH_RE.match(path)
    if block_match:
        content: Content | None = getattr(question, block_match.group(1), None)
        blocks = content.blocks if content is not None else []
        index = int(block_match.group(2))
        if index >= len(blocks):
            return None
        return blocks[index].to_dict()
    choice_match = _CHOICE_PATH_RE.match(path)
    if choice_match:
        choices = question.choices or []
        index = int(choice_match.group(1))
        if index >= len(choices):
            return None
        return choices[index].content.to_dict()
    raise ValueError(f"Unsupported quality-finding field path: {path!r}")


@dataclass(frozen=True, slots=True)
class QualityFinding:
    """One revision-bound quality finding.

    ``input_fingerprints`` maps every field path the rule read to the
    fingerprint of its value at detection time. A finding is current only
    while every declared dependency still matches; the target field is one
    of those dependencies but never the only one, which is what makes
    cross-field rules safe. ``repair`` is preview-only data and applying it
    is always the caller's explicit choice.
    """

    question_id: str
    target_field: str
    rule_id: str
    ruleset_version: str
    input_fingerprints: tuple[tuple[str, str], ...]
    severity: str
    explanation: str
    repair: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "question_id": self.question_id,
            "target_field": self.target_field,
            "rule_id": self.rule_id,
            "ruleset_version": self.ruleset_version,
            "input_fingerprints": [
                {"path": path, "fingerprint": fingerprint}
                for path, fingerprint in self.input_fingerprints
            ],
            "severity": self.severity,
            "explanation": self.explanation,
        }
        if self.repair is not None:
            data["repair"] = self.repair
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityFinding:
        unknown = sorted(set(data) - _FINDING_FIELDS)
        if unknown:
            raise ValueError(f"Unknown quality-finding field(s): {', '.join(unknown)}.")
        severity = str(data["severity"])
        if severity not in SEVERITIES:
            raise ValueError(f"Unsupported severity: {severity!r}")
        fingerprints = tuple(
            (str(item["path"]), str(item["fingerprint"]))
            for item in data["input_fingerprints"]
        )
        return cls(
            question_id=str(data["question_id"]),
            target_field=str(data["target_field"]),
            rule_id=str(data["rule_id"]),
            ruleset_version=str(data["ruleset_version"]),
            input_fingerprints=fingerprints,
            severity=severity,
            explanation=str(data["explanation"]),
            repair=data.get("repair"),
        )

    def fingerprint(self) -> str:
        """Return the fingerprint of the finding's own serialized form."""
        return field_fingerprint(self.to_dict())


def finding_state(finding: QualityFinding, question: Question) -> str:
    """Return ``current`` or ``stale`` for a finding against a question.

    A finding is stale when the question id changed, the ruleset version
    differs from the active one, any declared input dependency no longer
    resolves, or its recomputed fingerprint differs. Unrelated fields are
    never consulted, so an unrelated edit does not invalidate a finding.
    """
    if finding.question_id != question.id:
        return STATE_STALE
    if finding.ruleset_version != RULESET_VERSION:
        return STATE_STALE
    for path, expected in finding.input_fingerprints:
        try:
            value = _resolve_field_path(question, path)
        except ValueError:
            return STATE_STALE
        if value is None or field_fingerprint(value) != expected:
            return STATE_STALE
    return STATE_CURRENT


@dataclass(frozen=True, slots=True)
class QualityJudgment:
    """A recorded human decision over one finding.

    The judgment binds the finding's own fingerprint, so replaying it against
    an edited finding is detectable, and mirrors the ruleset version for
    auditing. No timestamp is stored: determinism of fixtures comes first,
    and callers can add provenance in their own envelopes.
    """

    finding: QualityFinding
    decision: str
    finding_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "finding": self.finding.to_dict(),
            "finding_fingerprint": self.finding_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityJudgment:
        unknown = sorted(set(data) - _JUDGMENT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown quality-judgment field(s): {', '.join(unknown)}.")
        finding = QualityFinding.from_dict(data["finding"])
        decision = str(data["decision"])
        if decision not in DECISIONS:
            raise ValueError(f"Unsupported decision: {decision!r}")
        return cls(
            finding=finding,
            decision=decision,
            finding_fingerprint=str(data["finding_fingerprint"]),
        )


def judge_finding(
    finding: QualityFinding, question: Question, decision: str
) -> QualityJudgment:
    """Record a human decision over a finding, failing closed on staleness.

    Accepting or rejecting a finding is only meaningful for content the
    finding still matches. When ``finding_state`` reports anything other
    than ``current`` this raises :class:`StaleFindingError` instead of
    silently applying an outdated judgment.
    """
    if decision not in DECISIONS:
        raise ValueError(f"Unsupported decision: {decision!r}")
    if finding_state(finding, question) != STATE_CURRENT:
        raise StaleFindingError(
            "The finding is stale: the question no longer matches the "
            "fingerprinted content the rule read. Re-run detection before "
            "recording a judgment."
        )
    return QualityJudgment(
        finding=finding,
        decision=decision,
        finding_fingerprint=finding.fingerprint(),
    )


def _iter_math_blocks(question: Question):
    """Yield ``(field_path, latex)`` pairs for every math block in scope."""
    for field_name in ("stem", "solution"):
        content = getattr(question, field_name, None)
        for index, block in enumerate(content.blocks if content else []):
            if block.type == "math" and block.latex is not None:
                yield f"{field_name}.blocks[{index}]", block.latex
    for choice_index, choice in enumerate(question.choices or []):
        for block in choice.content.blocks:
            if block.type == "math" and block.latex is not None:
                yield f"choices[{choice_index}].content", block.latex


def detect_quality_findings(question: Question) -> list[QualityFinding]:
    """Run the deterministic LaTeX rules over a question's math blocks.

    Every failing source becomes one finding bound to its block path and
    fingerprinted inputs. Sources with a deterministic repair additionally
    carry preview-only repair data (rule id and proposed LaTeX) so a
    reviewer can see the suggestion without anything being rewritten.
    """
    findings: list[QualityFinding] = []
    for path, latex in _iter_math_blocks(question):
        outcome = repair_latex_source(latex)
        if not outcome.repaired and outcome.finding_code is None:
            continue
        fingerprint = field_fingerprint(_resolve_field_path(question, path))
        if outcome.repaired:
            findings.append(
                QualityFinding(
                    question_id=question.id,
                    target_field=path,
                    rule_id=outcome.rule_id or "",
                    ruleset_version=RULESET_VERSION,
                    input_fingerprints=((path, fingerprint),),
                    severity="warning",
                    explanation=(
                        "A deterministic repair is proposed for this formula; "
                        "review the preview before accepting it."
                    ),
                    repair={
                        "rule_id": outcome.rule_id,
                        "source": outcome.source,
                        "latex": outcome.latex,
                        "applied_rules": list(outcome.applied_rules),
                    },
                )
            )
        else:
            findings.append(
                QualityFinding(
                    question_id=question.id,
                    target_field=path,
                    rule_id=outcome.finding_code or "",
                    ruleset_version=RULESET_VERSION,
                    input_fingerprints=((path, fingerprint),),
                    severity="error",
                    explanation=outcome.finding_message or "",
                )
            )
    return findings


