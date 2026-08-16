"""Executable fixture suite for the current schema and migration harness."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from dq_questionbank import (
    QuestionSet,
    SchemaVersionError,
    migrate,
    register_migration,
    validate_with_schema,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "compatibility"


def read_fixture(relative_path: str) -> dict:
    return json.loads((FIXTURES / relative_path).read_text(encoding="utf-8"))


def upgrade_fixture_versions(payload: dict) -> dict:
    upgraded = copy.deepcopy(payload)
    upgraded["schema_version"] = "1.0"
    for question in upgraded.get("questions", []):
        question["schema_version"] = "1.0"
    return upgraded


class CompatibilityFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        import dq_questionbank.migration as migration_module

        self.migration_module = migration_module
        self.saved_migrations = dict(migration_module._MIGRATIONS)
        migration_module._MIGRATIONS.clear()

    def tearDown(self) -> None:
        self.migration_module._MIGRATIONS.clear()
        self.migration_module._MIGRATIONS.update(self.saved_migrations)

    def test_current_schema_fixture_round_trips_without_issues(self):
        fixture = read_fixture("schema-1.0/question-set.json")
        self.assertEqual([], validate_with_schema(fixture))
        self.assertEqual(fixture, QuestionSet.from_dict(fixture).to_dict())

    def test_migration_fixture_requires_explicit_registration(self):
        fixture = read_fixture("migrations/0.9-to-1.0.json")
        with self.assertRaises(SchemaVersionError):
            migrate(fixture["source"], fixture["to_version"])

        @register_migration(fixture["from_version"], fixture["to_version"])
        def fixture_migration(payload):
            return upgrade_fixture_versions(payload)

        migrated = migrate(fixture["source"], fixture["to_version"])
        self.assertEqual(fixture["expected"], migrated)
        self.assertEqual([], validate_with_schema(migrated))
