"""Stable extension interfaces for importers, exporters, storage, and AI adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .models import QuestionSet


@runtime_checkable
class QuestionImporter(Protocol):
    format_name: str
    extensions: tuple[str, ...]

    def load(self, source: Path, **options: Any) -> QuestionSet: ...


@runtime_checkable
class QuestionExporter(Protocol):
    format_name: str
    extensions: tuple[str, ...]

    def dump(self, question_set: QuestionSet, target: Path, **options: Any) -> None: ...


@runtime_checkable
class StorageAdapter(Protocol):
    def save(self, question_set: QuestionSet) -> None: ...

    def load(self, question_set_id: str) -> QuestionSet: ...


@runtime_checkable
class AIProvider(Protocol):
    """Optional private integration point; the core never calls a provider directly."""

    def enrich(self, question_set: QuestionSet, **options: Any) -> QuestionSet: ...
