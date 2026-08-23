"""Configurable document-to-question field mapping.

Different sources label the same question fields differently — ``Prompt``
vs ``Question``, ``Explanation`` vs ``Rationale``. This module applies an
explicit mapping configuration to labeled source documents so an adapter
can be adjusted without changing the canonical model.

- :func:`load_mapping` reads a mapping configuration (source label ->
  canonical field, plus documented aliases and required fields);
- :func:`apply_mapping` converts labeled source records into canonical
  question dictionaries, reporting unmapped labels for review instead of
  silently discarding them;
- unmapped content rides along on ``unmapped_labels`` so a reviewer sees
  exactly what the mapping did not cover.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CANONICAL_FIELDS = {
    "stem",
    "choices",
    "answer",
    "analysis",
    "solution",
    "subject",
    "language",
}

_REQUIRED_FIELDS = ("stem",)


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """An explicit source-label to canonical-field mapping."""

    labels: tuple[tuple[str, str], ...]
    set_id: str = "mapped-import"
    set_title: str = "Mapped import"
    language: str = "en"

    def canonical_field_for(self, label: str) -> str | None:
        for source, target in self.labels:
            if source == label:
                return target
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_id": self.set_id,
            "set_title": self.set_title,
            "language": self.language,
            "labels": [
                {"source": source, "canonical": target}
                for source, target in self.labels
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldMapping:
        unknown = sorted(set(data) - {"set_id", "set_title", "language", "labels"})
        if unknown:
            raise ValueError(f"Unknown mapping field(s): {', '.join(unknown)}.")
        labels: list[tuple[str, str]] = []
        seen_sources: set[str] = set()
        for entry in data["labels"]:
            source = str(entry["source"])
            target = str(entry["canonical"])
            if target not in CANONICAL_FIELDS:
                raise ValueError(
                    f"Mapping target {target!r} is not a canonical question field."
                )
            if source in seen_sources:
                raise ValueError(f"Duplicate mapping source label: {source!r}.")
            seen_sources.add(source)
            labels.append((source, target))
        return cls(
            labels=tuple(labels),
            set_id=str(data.get("set_id", "mapped-import")),
            set_title=str(data.get("set_title", "Mapped import")),
            language=str(data.get("language", "en")),
        )


def load_mapping(path: Path) -> FieldMapping:
    """Load a mapping configuration from a JSON document."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return FieldMapping.from_dict(payload)


def apply_mapping(
    mapping: FieldMapping, records: list[dict[str, Any]]
) -> dict[str, Any]:
    """Convert labeled source records into a canonical question set.

    Returns ``{"question_set": ..., "unmapped_labels": ...}``. Unmapped
    labels are reported per question for review rather than silently
    discarded; a record with no mapped stem at all is reported as
    ``unmapped_records`` so nothing disappears quietly.
    """
    questions: list[dict[str, Any]] = []
    unmapped_labels: list[dict[str, Any]] = []
    unmapped_records: list[int] = []
    for index, record in enumerate(records):
        mapped: dict[str, Any] = {}
        metadata: dict[str, Any] = {}
        extra: list[str] = []
        for label, value in record.items():
            target = mapping.canonical_field_for(label)
            if target is None:
                extra.append(label)
                continue
            if target == "choices" and isinstance(value, list):
                mapped["choices"] = [
                    {"id": choice.get("id", ""), "content": {"blocks": [
                        {"type": "text", "text": str(choice.get("text", ""))}
                    ]}}
                    for choice in value
                ]
            elif target == "stem":
                mapped["stem"] = {"blocks": [{"type": "text", "text": str(value)}]}
            elif target == "solution":
                mapped["solution"] = {"blocks": [{"type": "text", "text": str(value)}]}
            elif target == "answer":
                mapped["answer"] = {"kind": "text", "value": str(value)}
            elif target == "analysis":
                metadata["analysis"] = str(value)
            else:
                mapped[target] = str(value)
        if extra:
            unmapped_labels.append({"record": index, "labels": extra})
        if "stem" not in mapped:
            unmapped_records.append(index)
            continue
        question = {
            "schema_version": "1.0",
            "id": f"q-{mapping.set_id}-{index + 1}",
            "type": "single_choice" if "choices" in mapped else "short_answer",
            "language": mapping.language,
        }
        question.update(mapped)
        question.setdefault("answer", {"kind": "text", "value": ""})
        if metadata:
            question["metadata"] = metadata
        questions.append(question)
    question_set = {
        "schema_version": "1.0",
        "id": mapping.set_id,
        "title": mapping.set_title,
        "language": mapping.language,
        "questions": questions,
    }
    return {
        "question_set": question_set,
        "unmapped_labels": unmapped_labels,
        "unmapped_records": unmapped_records,
    }
