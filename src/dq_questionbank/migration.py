"""Schema version migration framework for forward-compatible data evolution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .exceptions import SchemaVersionError

MigrationFunc = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: dict[str, dict[str, MigrationFunc]] = {}


def register_migration(from_version: str, to_version: str) -> Callable[[MigrationFunc], MigrationFunc]:
    """Decorator to register a migration from one schema version to another."""

    def decorator(func: MigrationFunc) -> MigrationFunc:
        _MIGRATIONS.setdefault(from_version, {})[to_version] = func
        return func

    return decorator


def migrate(payload: dict[str, Any], target_version: str) -> dict[str, Any]:
    """Apply registered migrations to bring a payload to the target schema version.

    Raises SchemaVersionError when no migration path exists.
    """
    current = payload.get("schema_version")
    if current is None:
        raise SchemaVersionError("Payload has no schema_version; cannot migrate.")
    if current == target_version:
        return payload

    visited: set[str] = set()
    data = dict(payload)
    while data.get("schema_version") != target_version:
        ver = data.get("schema_version")
        if ver in visited:
            raise SchemaVersionError(f"Circular migration detected at version {ver}.")
        visited.add(ver)

        candidates = _MIGRATIONS.get(ver, {})
        if target_version in candidates:
            data = candidates[target_version](data)
            continue
        if not candidates:
            raise SchemaVersionError(
                f"No migrations registered from schema version {ver}."
            )
        next_ver = sorted(candidates.keys())[0]
        data = candidates[next_ver](data)

    return data


def list_migrations() -> dict[str, list[str]]:
    """Return all registered migration paths as {from_version: [to_versions]}."""
    return {src: sorted(dests) for src, dests in _MIGRATIONS.items()}
