"""Access to the installed normative JSON Schema files."""

from __future__ import annotations

import json
import sysconfig
from pathlib import Path
from typing import Any

from .exceptions import SchemaNotFoundError, SchemaVersionError
from .models import SUPPORTED_SCHEMA_VERSIONS

SCHEMA_FILENAMES = {
    "1.0": "question-set.schema.json",
    "1.1": "question-set-1.1.schema.json",
}


def _filename_for(version: str) -> str:
    if version not in SCHEMA_FILENAMES:
        raise SchemaVersionError(
            f"Schema version {version!r} is not supported; expected one of: "
            + ", ".join(SUPPORTED_SCHEMA_VERSIONS)
            + "."
        )
    return SCHEMA_FILENAMES[version]


def schema_path(version: str = "1.0") -> Path:
    """Return the schema file for ``version`` in the active Python environment."""
    filename = _filename_for(version)
    installed = (
        Path(sysconfig.get_path("data"))
        / "share"
        / "dq-questionbank-core"
        / "schema"
        / filename
    )
    if installed.is_file():
        return installed
    source_checkout = Path(__file__).resolve().parents[2] / "schema" / filename
    return source_checkout if source_checkout.is_file() else installed


def load_schema(version: str = "1.0") -> dict[str, Any]:
    """Load the installed JSON Schema for ``version`` or raise a clear error."""
    path = schema_path(version)
    if not path.is_file():
        raise SchemaNotFoundError(
            "The DQ Question Schema is missing from this installation. "
            "Reinstall dq-questionbank-core from an official distribution."
        )
    return json.loads(path.read_text(encoding="utf-8"))
