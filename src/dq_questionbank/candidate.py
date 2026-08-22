from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dq_questionbank.interfaces import QuestionImporter
from dq_questionbank.models import (
    Answer,
    Content,
    ContentBlock,
    Question,
    QuestionSet,
    SourceMetadata,
)


@dataclass
class FieldEvidence:
    source_locator: str
    confidence: float = 1.0
    raw_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "source_locator": self.source_locator,
            "confidence": self.confidence,
        }
        if self.raw_text is not None:
            result["raw_text"] = self.raw_text
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldEvidence:
        return cls(
            source_locator=str(data.get("source_locator", "unknown")),
            confidence=float(data.get("confidence", 1.0)),
            raw_text=data.get("raw_text"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class CandidateField:
    name: str
    value: Any
    evidence: FieldEvidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "evidence": self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> CandidateField:
        ev_data = data.get("evidence", {})
        evidence = (
            FieldEvidence.from_dict(ev_data)
            if isinstance(ev_data, dict)
            else FieldEvidence(source_locator="unknown")
        )
        val = data.get("value", data) if "value" in data else data
        return cls(name=name, value=val, evidence=evidence)


@dataclass
class CandidateQuestion:
    candidate_id: str
    status: str
    source_evidence: dict[str, Any]
    extracted_fields: dict[str, CandidateField]
    reviewer_notes: str | None = None

    def get_field_evidence(self, field_name: str) -> FieldEvidence | None:
        c_field = self.extracted_fields.get(field_name)
        return c_field.evidence if c_field else None

    def to_canonical_question(self) -> Question:
        blocks: list[ContentBlock] = []

        stem_field = self.extracted_fields.get("stem")
        if stem_field:
            stem_val = stem_field.value
            if isinstance(stem_val, dict):
                if "text" in stem_val:
                    blocks.append(ContentBlock(type="text", text=str(stem_val["text"])))
                if "latex_formula" in stem_val:
                    blocks.append(ContentBlock(type="math", latex=str(stem_val["latex_formula"])))
            elif isinstance(stem_val, str):
                blocks.append(ContentBlock(type="text", text=stem_val))

        formula_field = self.extracted_fields.get("formula")
        if formula_field:
            f_val = formula_field.value
            latex_str = f_val.get("latex") if isinstance(f_val, dict) else str(f_val)
            blocks.append(ContentBlock(type="math", latex=latex_str))

        table_field = self.extracted_fields.get("table")
        if table_field:
            t_val = table_field.value
            rows = t_val.get("rows") if isinstance(t_val, dict) else t_val
            if isinstance(rows, list):
                blocks.append(ContentBlock(type="table", rows=rows))

        answer_field = self.extracted_fields.get("answer")
        ans_obj = None
        if answer_field:
            ans_val = answer_field.value
            if isinstance(ans_val, dict):
                ans_kind = str(ans_val.get("kind", "text"))
                ans_v = str(ans_val.get("value", ""))
            else:
                ans_kind = "text"
                ans_v = str(ans_val)
            ans_obj = Answer(kind=ans_kind, value=ans_v)

        doc = str(self.source_evidence.get("document", "PDF Intake"))
        page = self.source_evidence.get("page_number")
        locator = f"page {page}" if page is not None else str(self.source_evidence.get("locator", ""))
        src_meta = SourceMetadata(
            title=doc,
            locator=locator,
            attribution="Extracted via PDF intake pipeline",
        )

        return Question(
            id=self.candidate_id,
            type="short_answer",
            stem=Content(blocks=blocks),
            answer=ans_obj,
            source=src_meta,
            metadata={"candidate_id": self.candidate_id, "intake_status": self.status},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status,
            "source_evidence": self.source_evidence,
            "extracted_fields": {k: v.to_dict() for k, v in self.extracted_fields.items()},
            "reviewer_notes": self.reviewer_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateQuestion:
        fields = {}
        raw_fields = data.get("extracted_fields", {})
        for fname, fval in raw_fields.items():
            if isinstance(fval, dict) and "evidence" in fval:
                fields[fname] = CandidateField.from_dict(fname, fval)
            else:
                fields[fname] = CandidateField(
                    name=fname,
                    value=fval,
                    evidence=FieldEvidence(source_locator=f"extracted_{fname}"),
                )
        return cls(
            candidate_id=data["candidate_id"],
            status=data.get("status", "pending"),
            source_evidence=dict(data.get("source_evidence", {})),
            extracted_fields=fields,
            reviewer_notes=data.get("reviewer_notes"),
        )


class CandidateSession:
    def __init__(self, session_id: str, candidates: list[CandidateQuestion] | None = None):
        self.session_id = session_id
        self.candidates: list[CandidateQuestion] = candidates or []

    def get_candidate(self, candidate_id: str) -> CandidateQuestion | None:
        for c in self.candidates:
            if c.candidate_id == candidate_id:
                return c
        return None

    def review_candidate(
        self, candidate_id: str, decision: str, reviewer_notes: str | None = None
    ) -> CandidateQuestion:
        if decision not in ("accepted", "rejected", "pending"):
            raise ValueError(
                f"Invalid review decision: {decision}. Must be 'accepted', 'rejected', or 'pending'."
            )
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(f"Candidate not found: {candidate_id}")
        candidate.status = decision
        if reviewer_notes is not None:
            candidate.reviewer_notes = reviewer_notes
        return candidate

    def to_question_set(
        self, set_id: str = "intake-set", title: str = "Imported Candidate Set"
    ) -> QuestionSet:
        questions = [c.to_canonical_question() for c in self.candidates if c.status == "accepted"]
        return QuestionSet(
            id=set_id,
            title=title,
            questions=questions,
            language="en",
            metadata={"session_id": self.session_id},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "candidates": [c.to_dict() for c in self.candidates],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateSession:
        session_id = data.get("session_id", "intake-session")
        c_list = [CandidateQuestion.from_dict(c) for c in data.get("candidates", [])]
        return cls(session_id=session_id, candidates=c_list)


class IntakeCandidateImporter(QuestionImporter):
    format_name = "intake_candidate"
    extensions = (".json",)

    def load_session(self, source: Path | str | dict[str, Any]) -> CandidateSession:
        if isinstance(source, (str, Path)):
            path = Path(source)
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = source
        return CandidateSession.from_dict(data)

    def load(self, path: Path) -> QuestionSet:
        session = self.load_session(path)
        for c in session.candidates:
            if c.status == "pending":
                c.status = "accepted"
        return session.to_question_set()
