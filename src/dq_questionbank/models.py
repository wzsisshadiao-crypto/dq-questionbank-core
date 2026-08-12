"""Canonical, serializable data model for educational questions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0"
QUESTION_TYPES = {
    "single_choice",
    "multiple_choice",
    "true_false",
    "fill_blank",
    "short_answer",
    "essay",
    "composite",
}
BLOCK_TYPES = {"text", "math", "image", "table", "code", "line_break"}


def _copy_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass(slots=True)
class ContentBlock:
    type: str = "text"
    text: str | None = None
    latex: str | None = None
    asset_id: str | None = None
    alt_text: str | None = None
    language: str | None = None
    rows: list[list[str]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentBlock:
        return cls(
            type=str(data.get("type", "text")),
            text=data.get("text"),
            latex=data.get("latex"),
            asset_id=data.get("asset_id"),
            alt_text=data.get("alt_text"),
            language=data.get("language"),
            rows=data.get("rows"),
            metadata=_copy_mapping(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value not in (None, {}, [])}


@dataclass(slots=True)
class Content:
    blocks: list[ContentBlock] = field(default_factory=list)

    @classmethod
    def text(cls, value: str, language: str | None = None) -> Content:
        return cls([ContentBlock(type="text", text=value, language=language)])

    @classmethod
    def from_dict(cls, data: Any) -> Content:
        if isinstance(data, str):
            return cls.text(data)
        if not isinstance(data, dict):
            return cls()
        return cls([ContentBlock.from_dict(item) for item in data.get("blocks", [])])

    def to_dict(self) -> dict[str, Any]:
        return {"blocks": [block.to_dict() for block in self.blocks]}

    def plain_text(self) -> str:
        rendered: list[str] = []
        for block in self.blocks:
            if block.type in {"text", "code"}:
                rendered.append(block.text or "")
            elif block.type == "math":
                rendered.append(f"${block.latex or ''}$")
            elif block.type == "image":
                rendered.append(f"[{block.alt_text or 'image'}]")
            elif block.type == "table":
                rendered.extend(" | ".join(row) for row in (block.rows or []))
            elif block.type == "line_break":
                rendered.append("\n")
        return "".join(rendered)


@dataclass(slots=True)
class Asset:
    id: str
    kind: str
    uri: str
    media_type: str | None = None
    sha256: str | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Asset:
        return cls(
            id=str(data.get("id", "")),
            kind=str(data.get("kind", "image")),
            uri=str(data.get("uri", "")),
            media_type=data.get("media_type"),
            sha256=data.get("sha256"),
            width=data.get("width"),
            height=data.get("height"),
            metadata=_copy_mapping(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value not in (None, {}, [])}


@dataclass(slots=True)
class Choice:
    id: str
    content: Content
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Choice:
        return cls(
            id=str(data.get("id", "")),
            content=Content.from_dict(data.get("content")),
            metadata=_copy_mapping(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "content": self.content.to_dict()}
        if self.metadata:
            data["metadata"] = self.metadata
        return data


@dataclass(slots=True)
class Answer:
    kind: str
    value: Any
    alternatives: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> Answer | None:
        if data is None:
            return None
        if not isinstance(data, dict):
            return cls(kind="text", value=data)
        return cls(
            kind=str(data.get("kind", "text")),
            value=data.get("value"),
            alternatives=list(data.get("alternatives", [])),
            metadata=_copy_mapping(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"kind": self.kind, "value": self.value}
        if self.alternatives:
            data["alternatives"] = self.alternatives
        if self.metadata:
            data["metadata"] = self.metadata
        return data


@dataclass(slots=True)
class SourceMetadata:
    title: str | None = None
    author: str | None = None
    year: int | None = None
    uri: str | None = None
    license: str | None = None
    attribution: str | None = None
    locator: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> SourceMetadata | None:
        if not isinstance(data, dict):
            return None
        known = {"title", "author", "year", "uri", "license", "attribution", "locator"}
        return cls(
            title=data.get("title"),
            author=data.get("author"),
            year=data.get("year"),
            uri=data.get("uri"),
            license=data.get("license"),
            attribution=data.get("attribution"),
            locator=data.get("locator"),
            metadata={key: value for key, value in data.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        metadata = data.pop("metadata")
        output = {key: value for key, value in data.items() if value is not None}
        output.update(metadata)
        return output


@dataclass(slots=True)
class TaxonomyRef:
    system: str
    code: str
    label: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaxonomyRef:
        return cls(str(data.get("system", "")), str(data.get("code", "")), data.get("label"))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(slots=True)
class Question:
    id: str
    type: str
    stem: Content
    language: str = "en"
    subject: str | None = None
    choices: list[Choice] = field(default_factory=list)
    answer: Answer | None = None
    solution: Content | None = None
    hints: list[Content] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    difficulty: float | None = None
    source: SourceMetadata | None = None
    taxonomy: list[TaxonomyRef] = field(default_factory=list)
    subquestions: list[Question] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Question:
        return cls(
            id=str(data.get("id", "")),
            type=str(data.get("type", "short_answer")),
            stem=Content.from_dict(data.get("stem")),
            language=str(data.get("language", "en")),
            subject=data.get("subject"),
            choices=[Choice.from_dict(item) for item in data.get("choices", [])],
            answer=Answer.from_dict(data.get("answer")),
            solution=Content.from_dict(data["solution"])
            if data.get("solution") is not None
            else None,
            hints=[Content.from_dict(item) for item in data.get("hints", [])],
            assets=[Asset.from_dict(item) for item in data.get("assets", [])],
            tags=[str(item) for item in data.get("tags", [])],
            difficulty=data.get("difficulty"),
            source=SourceMetadata.from_dict(data.get("source")),
            taxonomy=[TaxonomyRef.from_dict(item) for item in data.get("taxonomy", [])],
            subquestions=[cls.from_dict(item) for item in data.get("subquestions", [])],
            metadata=_copy_mapping(data.get("metadata")),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "type": self.type,
            "language": self.language,
            "stem": self.stem.to_dict(),
        }
        optional = {
            "subject": self.subject,
            "choices": [item.to_dict() for item in self.choices],
            "answer": self.answer.to_dict() if self.answer else None,
            "solution": self.solution.to_dict() if self.solution else None,
            "hints": [item.to_dict() for item in self.hints],
            "assets": [item.to_dict() for item in self.assets],
            "tags": self.tags,
            "difficulty": self.difficulty,
            "source": self.source.to_dict() if self.source else None,
            "taxonomy": [item.to_dict() for item in self.taxonomy],
            "subquestions": [item.to_dict() for item in self.subquestions],
            "metadata": self.metadata,
        }
        data.update({key: value for key, value in optional.items() if value not in (None, [], {})})
        return data


@dataclass(slots=True)
class QuestionSet:
    id: str
    title: str
    questions: list[Question] = field(default_factory=list)
    description: str | None = None
    language: str = "en"
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Any) -> QuestionSet:
        if isinstance(data, list):
            data = {"id": "imported", "title": "Imported questions", "questions": data}
        if not isinstance(data, dict):
            raise TypeError("Question data must be an object or an array.")
        if "questions" not in data and "id" in data and "stem" in data:
            data = {"id": "imported", "title": "Imported question", "questions": [data]}
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            questions=[Question.from_dict(item) for item in data.get("questions", [])],
            description=data.get("description"),
            language=str(data.get("language", "en")),
            metadata=_copy_mapping(data.get("metadata")),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "title": self.title,
            "language": self.language,
            "questions": [question.to_dict() for question in self.questions],
        }
        if self.description:
            data["description"] = self.description
        if self.metadata:
            data["metadata"] = self.metadata
        return data
