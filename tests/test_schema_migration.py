"""Built-in schema 1.0 -> 1.1 migration and multi-version validation."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from dq_questionbank import (
    LATEST_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    QuestionSet,
    SchemaVersionError,
    list_migrations,
    migrate,
    register_migration,
    validate_with_schema,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "compatibility"


def read_fixture(relative_path: str) -> dict:
    return json.loads((FIXTURES / relative_path).read_text(encoding="utf-8"))


class BuiltinSchemaMigrationTests(unittest.TestCase):
    def test_builtin_path_is_registered(self):
        self.assertEqual(["1.1"], list_migrations()["1.0"])
        self.assertEqual("1.1", LATEST_SCHEMA_VERSION)
        self.assertEqual(("1.0", "1.1"), SUPPORTED_SCHEMA_VERSIONS)

    def test_fixture_migration_promotes_analysis_and_validates(self):
        fixture = read_fixture("migrations/1.0-to-1.1.json")
        original = copy.deepcopy(fixture["source"])

        migrated = migrate(fixture["source"], fixture["to_version"])

        self.assertEqual(fixture["expected"], migrated)
        self.assertEqual([], validate_with_schema(migrated))
        self.assertEqual(migrated, QuestionSet.from_dict(migrated).to_dict())
        self.assertEqual(
            fixture["source"], original, "migration never mutates the input payload"
        )

    def test_migrated_analysis_survives_the_model_round_trip(self):
        fixture = read_fixture("migrations/1.0-to-1.1.json")
        question_set = QuestionSet.from_dict(migrate(fixture["source"], "1.1"))

        analysis = question_set.questions[0].analysis
        self.assertIsNotNone(analysis)
        self.assertEqual("text", analysis.blocks[0].type)
        self.assertIn("Factor", analysis.blocks[0].text)
        self.assertIsNone(question_set.questions[1].analysis)

    def test_payload_without_analysis_only_bumps_versions(self):
        payload = {
            "schema_version": "1.0",
            "id": "plain",
            "title": "Plain",
            "language": "en",
            "questions": [
                {
                    "schema_version": "1.0",
                    "id": "q1",
                    "type": "short_answer",
                    "language": "en",
                    "stem": {"blocks": [{"type": "text", "text": "Plain."}]},
                    "metadata": {"workspace_hint": "keep"},
                }
            ],
        }
        original = copy.deepcopy(payload)

        migrated = migrate(payload, "1.1")

        self.assertEqual("1.1", migrated["schema_version"])
        self.assertEqual("1.1", migrated["questions"][0]["schema_version"])
        self.assertEqual({"workspace_hint": "keep"}, migrated["questions"][0]["metadata"])
        self.assertNotIn("analysis", migrated["questions"][0])
        self.assertEqual(payload, original)

    def test_already_migrated_payload_returns_equal_copy(self):
        fixture = read_fixture("migrations/1.0-to-1.1.json")
        expected = fixture["expected"]

        result = migrate(expected, "1.1")

        self.assertEqual(expected, result)
        self.assertIsNot(expected, result)

    def test_1_0_documents_remain_valid_without_migration(self):
        fixture = read_fixture("migrations/1.0-to-1.1.json")
        self.assertEqual([], validate_with_schema(fixture["source"]))

    def test_validate_with_schema_rejects_unknown_declared_version(self):
        payload = {
            "schema_version": "2.0",
            "id": "x",
            "title": "X",
            "language": "en",
            "questions": [],
        }
        issues = validate_with_schema(payload)
        self.assertTrue(any(issue.code == "unsupported_schema" for issue in issues))

    def test_unknown_target_version_is_rejected(self):
        with self.assertRaises(SchemaVersionError):
            migrate({"schema_version": "1.0", "questions": []}, "9.9")


class MigrationPathSelectionTests(unittest.TestCase):
    def setUp(self):
        import dq_questionbank.migration as mod

        self.mod = mod
        self._saved = copy.deepcopy(mod._MIGRATIONS)
        mod._MIGRATIONS.clear()

    def tearDown(self):
        self.mod._MIGRATIONS.clear()
        self.mod._MIGRATIONS.update(self._saved)

    def test_ambiguous_fork_is_rejected_instead_of_guessed(self):
        @register_migration("1.0", "1.5")
        def _to_1_5(data):
            data["schema_version"] = "1.5"
            return data

        @register_migration("1.0", "2.0")
        def _to_2_0(data):
            data["schema_version"] = "2.0"
            return data

        with self.assertRaisesRegex(SchemaVersionError, "Ambiguous migration"):
            migrate({"schema_version": "1.0"}, "3.0")

    def test_non_forward_hop_is_rejected(self):
        @register_migration("1.0", "2.0")
        def _to_2_0(data):
            data["schema_version"] = "2.0"
            return data

        with self.assertRaises(SchemaVersionError):
            migrate({"schema_version": "1.0"}, "1.5")


if __name__ == "__main__":
    unittest.main()
