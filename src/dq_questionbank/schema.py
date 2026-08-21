"""Access to the installed normative JSON Schema."""

from __future__ import annotations

import json
import sysconfig
from pathlib import Path
from typing import Any

from .exceptions import SchemaNotFoundError


def schema_path() -> Path:
    """Return the schema installed in the active Python environment."""
    installed = (
        Path(sysconfig.get_path("data"))
        / "share"
        / "dq-questionbank-core"
        / "schema"
        / "question-set.schema.json"
    )
    if installed.is_file():
        return installed
    source_checkout = Path(__file__).resolve().parents[2] / "schema" / "question-set.schema.json"
    return source_checkout if source_checkout.is_file() else installed


def load_schema() -> dict[str, Any]:
    """Load the installed JSON Schema or raise a clear packaging error."""
    path = schema_path()
    if not path.is_file():
        raise SchemaNotFoundError(
            "The DQ Question Schema is missing from this installation. "
            "Reinstall dq-questionbank-core from an official distribution."
        )
    return json.loads(path.read_text(encoding="utf-8"))
