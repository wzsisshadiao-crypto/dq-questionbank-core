"""Schema version migration framework for forward-compatible data evolution."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from typing import Any

from .exceptions import SchemaVersionError

MigrationFunc = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: dict[str, dict[str, MigrationFunc]] = {}

_NUMERIC_VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")


def register_migration(from_version: str, to_version: str) -> Callable[[MigrationFunc], MigrationFunc]:
    """Decorator to register a migration from one schema version to another."""

    def decorator(func: MigrationFunc) -> MigrationFunc:
        _MIGRATIONS.setdefault(from_version, {})[to_version] = func
        return func

    return decorator


def _version_key(version: str) -> tuple[int, ...]:
    if not _NUMERIC_VERSION_RE.match(version):
        raise SchemaVersionError(
            f"Schema version {version!r} must use numeric major.minor components."
        )
    return tuple(int(part) for part in version.split("."))


def migrate(payload: dict[str, Any], target_version: str) -> dict[str, Any]:
    """Apply registered migrations to bring a payload to the target schema version.

    The caller's payload is never mutated. A direct edge to the target wins;
    otherwise the single unambiguous forward hop is taken. Unknown versions,
    dead ends, and ambiguous forks raise ``SchemaVersionError`` instead of
    guessing.
    """
    current = payload.get("schema_version")
    if current is None:
        raise SchemaVersionError("Payload has no schema_version; cannot migrate.")
    _version_key(target_version)
    if current == target_version:
        return copy.deepcopy(payload)

    visited: set[str] = set()
    data = copy.deepcopy(payload)
    while data.get("schema_version") != target_version:
        ver = data.get("schema_version")
        if ver in visited:
            raise SchemaVersionError(f"Circular migration detected at version {ver}.")
        visited.add(ver)

        candidates = _MIGRATIONS.get(ver, {})
        if not candidates:
            raise SchemaVersionError(f"No migrations registered from schema version {ver}.")
        if target_version in candidates:
            data = candidates[target_version](data)
            continue
        forward = sorted(
            (
                next_ver
                for next_ver in candidates
                if _version_key(next_ver) < _version_key(target_version)
            ),
            key=_version_key,
        )
        if not forward:
            raise SchemaVersionError(
                f"Migration from schema version {ver} cannot reach {target_version}: "
                f"every registered target {sorted(candidates)} is at or beyond it."
            )
        if len(forward) > 1:
            raise SchemaVersionError(
                f"Ambiguous migration from schema version {ver}: registered targets "
                f"{forward} all lead toward {target_version}; refusing to guess."
            )
        data = candidates[forward[0]](data)

    return data


def list_migrations() -> dict[str, list[str]]:
    """Return all registered migration paths as {from_version: [to_versions]}."""
    return {src: sorted(dests) for src, dests in _MIGRATIONS.items()}


def _migrate_question_1_0_to_1_1(question: dict[str, Any]) -> dict[str, Any]:
    data = dict(question)
    data["schema_version"] = "1.1"
    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        analysis = metadata.get("analysis")
        if isinstance(analysis, str) and analysis.strip():
            remaining = {key: value for key, value in metadata.items() if key != "analysis"}
            data["analysis"] = {"blocks": [{"type": "text", "text": analysis}]}
            if remaining:
                data["metadata"] = remaining
            else:
                data.pop("metadata", None)
    if data.get("subquestions"):
        data["subquestions"] = [
            _migrate_question_1_0_to_1_1(sub) for sub in data["subquestions"]
        ]
    return data


@register_migration("1.0", "1.1")
def _migrate_1_0_to_1_1(payload: dict[str, Any]) -> dict[str, Any]:
    """Promote question-level metadata.analysis to the schema 1.1 analysis field."""
    data = dict(payload)
    data["schema_version"] = "1.1"
    data["questions"] = [
        _migrate_question_1_0_to_1_1(question) for question in data.get("questions", [])
    ]
    return data
