"""Canonical JSON reader and writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import QuestionSet


class JsonImporter:
    format_name = "json"
    extensions = (".json",)

    def load(self, source: Path, **options: Any) -> QuestionSet:
        with source.open("r", encoding="utf-8-sig") as handle:
            return QuestionSet.from_dict(json.load(handle))


class JsonExporter:
    format_name = "json"
    extensions = (".json",)

    def dump(self, question_set: QuestionSet, target: Path, **options: Any) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(question_set.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
