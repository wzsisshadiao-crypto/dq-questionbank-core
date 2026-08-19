"""Candidate session models and intake importer for raw extraction payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dq_questionbank.interfaces import QuestionImporter
from dq_questionbank.models import Question, QuestionSet


@dataclass
class FieldEvidence:
    """Source evidence recording provenance for an extracted question field."""

    field_name: str
    source_locator: str
    page: int | None = None
    bbox: list[float] | None = None
    raw_segment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "field_name": self.field_name,
            "source_locator": self.source_locator,
        }
        if self.page is not None:
            data["page"] = self.page
        if self.bbox is not None:
            data["bbox"] = self.bbox
        if self.raw_segment is not None:
            data["raw_segment"] = self.raw_segment
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldEvidence:
        return cls(
            field_name=data["field_name"],
            source_locator=data.get("source_locator", "unknown"),
            page=data.get("page"),
            bbox=data.get("bbox"),
            raw_segment=data.get("raw_segment"),
        )


@dataclass
class CandidateQuestion:
    """An extracted question candidate with field evidence and review state."""

    candidate_id: str
    question: Question
    evidence: dict[str, FieldEvidence] = field(default_factory=dict)
    status: str = "pending"
    rejection_reason: str | None = None

    def accept(self) -> None:
        self.status = "accepted"
        self.rejection_reason = None

    def reject(self, reason: str | None = None) -> None:
        self.status = "rejected"
        self.rejection_reason = reason

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "question": self.question.to_dict(),
            "evidence": {k: v.to_dict() for k, v in self.evidence.items()},
            "status": self.status,
        }
        if self.rejection_reason:
            data["rejection_reason"] = self.rejection_reason
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateQuestion:
        evidence = {
            k: FieldEvidence.from_dict(v) for k, v in data.get("evidence", {}).items()
        }
        question = Question.from_dict(data.get("question", {}))
        return cls(
            candidate_id=data["candidate_id"],
            question=question,
            evidence=evidence,
            status=data.get("status", "pending"),
            rejection_reason=data.get("rejection_reason"),
        )


class CandidateSession:
    """An intake session holding candidate questions separate from canonical storage."""

    def __init__(
        self,
        session_id: str,
        source_document: str,
        candidates: list[CandidateQuestion] | None = None,
        title: str = "Intake Session",
        language: str = "en",
    ) -> None:
        self.session_id = session_id
        self.source_document = source_document
        self.title = title
        self.language = language
        self.candidates: list[CandidateQuestion] = candidates or []

    def get_candidate(self, candidate_id: str) -> CandidateQuestion | None:
        for candidate in self.candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        return None

    def accept_candidate(self, candidate_id: str) -> Question:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(f"Candidate {candidate_id} not found in session")
        candidate.accept()
        return candidate.question

    def reject_candidate(self, candidate_id: str, reason: str | None = None) -> None:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(f"Candidate {candidate_id} not found in session")
        candidate.reject(reason)

    def to_question_set(self) -> QuestionSet:
        """Construct a QuestionSet containing only accepted candidates."""
        accepted_questions = [
            candidate.question
            for candidate in self.candidates
            if candidate.status == "accepted"
        ]
        return QuestionSet(
            id=self.session_id,
            title=self.title,
            questions=accepted_questions,
            language=self.language,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "source_document": self.source_document,
            "title": self.title,
            "language": self.language,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateSession:
        candidates = [
            CandidateQuestion.from_dict(c) for c in data.get("candidates", [])
        ]
        return cls(
            session_id=data["session_id"],
            source_document=data.get("source_document", "unknown"),
            candidates=candidates,
            title=data.get("title", "Intake Session"),
            language=data.get("language", "en"),
        )


class IntakeImporter(QuestionImporter):
    """Importer that parses intake candidate session files."""

    format_name = "intake"
    extensions = (".json",)

    def create_session(self, path: Path) -> CandidateSession:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        return CandidateSession.from_dict(data)

    def load(self, path: Path) -> QuestionSet:
        session = self.create_session(path)
        for candidate in session.candidates:
            if candidate.status == "pending":
                candidate.accept()
        return session.to_question_set()
