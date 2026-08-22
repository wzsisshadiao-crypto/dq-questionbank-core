"""Public dataclass layer over reviewable import candidate sessions.

The digest-bound session document produced by :mod:`dq_questionbank.intake`
is the wire format; this module wraps it in stable public dataclasses so a
Review Center frontend can work with typed objects while the canonical
serialized form stays the single source of truth.

Guarantees carried over from the session layer:

- candidates are **extracted**, not accepted — no state in this module
  implies persistence or AI approval;
- pending / accepted / rejected decisions are explicit and fail closed
  against stale digests or already-reviewed candidates;
- every reviewed edit deterministically bumps the candidate ``revision``
  and rebinds its question digest;
- the session keeps the parser identity and source evidence it was
  extracted with.

``ImportCandidateSession.from_session`` verifies the digest before
wrapping, and ``to_session`` reproduces the exact canonical document, so
round-tripping never drifts.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from .intake import (
    _verify_session,
    export_reviewed_questions,
    review_import_session,
)
from .models import QuestionSet

DECISION_PENDING = "pending"
DECISION_ACCEPTED = "accepted"
DECISION_REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ImportCandidate:
    """One extracted candidate question inside a review session."""

    question_id: str
    status: str
    decision: str
    revision: int
    question: dict[str, Any]
    question_sha256: str
    evidence: tuple[dict[str, Any], ...]
    diagnostics: tuple[dict[str, Any], ...]

    @property
    def pending(self) -> bool:
        return self.decision == DECISION_PENDING


@dataclass(frozen=True, slots=True)
class ImportCandidateSession:
    """A typed view over one digest-bound candidate-session document."""

    document: dict[str, Any] = field(repr=False)
    candidates: tuple[ImportCandidate, ...] = ()

    @classmethod
    def from_session(cls, session: dict[str, Any]) -> ImportCandidateSession:
        verified = _verify_session(copy.deepcopy(session))
        candidates = tuple(
            ImportCandidate(
                question_id=str(item["question_id"]),
                status=str(item.get("status", "candidate_ready")),
                decision=str(item.get("decision", DECISION_PENDING)),
                revision=int(item.get("revision", 1)),
                question=item["question"],
                question_sha256=str(item["question_sha256"]),
                evidence=tuple(item.get("evidence") or []),
                diagnostics=tuple(item.get("diagnostics") or []),
            )
            for item in verified["candidates"]
        )
        return cls(document=verified, candidates=candidates)

    def to_session(self) -> dict[str, Any]:
        """Reproduce the canonical session document exactly."""
        return copy.deepcopy(self.document)

    @property
    def session_version(self) -> str:
        return str(self.document["session_version"])

    @property
    def bundle_id(self) -> str:
        return str(self.document["bundle_id"])

    @property
    def route(self) -> str:
        return str(self.document["route"])

    @property
    def parser_identity(self) -> str:
        return str((self.document.get("parser") or {}).get("identity", ""))

    @property
    def status(self) -> str:
        return str(self.document["status"])

    def decide(
        self, decisions: dict[str, Any]
    ) -> ImportCandidateSession:
        """Apply explicit review decisions and return the next session view.

        ``decisions`` follows the canonical ``review_import_session``
        document form (``{"decisions": [{"question_id": ...,
        "candidate_sha256": ..., "decision": "accepted" | "rejected",
        ...}]}``) and fails closed on stale or already-reviewed candidates.
        """
        reviewed = review_import_session(self.to_session(), decisions)
        return ImportCandidateSession.from_session(reviewed)

    def export_accepted(self) -> QuestionSet:
        """Export accepted candidates; never persist them."""
        return export_reviewed_questions(self.to_session())

    @property
    def pending(self) -> tuple[ImportCandidate, ...]:
        return tuple(item for item in self.candidates if item.pending)

    @property
    def accepted(self) -> tuple[ImportCandidate, ...]:
        return tuple(
            item for item in self.candidates if item.decision == DECISION_ACCEPTED
        )

    @property
    def rejected(self) -> tuple[ImportCandidate, ...]:
        return tuple(
            item for item in self.candidates if item.decision == DECISION_REJECTED
        )
