"""Tests for the schema version migration framework."""

from __future__ import annotations

import unittest

from dq_questionbank.exceptions import SchemaVersionError
from dq_questionbank.migration import list_migrations, migrate, register_migration


class MigrationTests(unittest.TestCase):
    def setUp(self):
        import dq_questionbank.migration as mod

        self._saved = dict(mod._MIGRATIONS)
        mod._MIGRATIONS.clear()

    def tearDown(self):
        import dq_questionbank.migration as mod

        mod._MIGRATIONS.clear()
        mod._MIGRATIONS.update(self._saved)

    def test_noop_when_already_target(self):
        result = migrate({"schema_version": "1.0"}, "1.0")
        self.assertEqual(result, {"schema_version": "1.0"})

    def test_direct_migration_applied(self):
        @register_migration("1.0", "2.0")
        def v1_to_v2(data):
            data["schema_version"] = "2.0"
            data["new_field"] = True
            return data

        result = migrate({"schema_version": "1.0", "id": "q1"}, "2.0")
        self.assertEqual(result["schema_version"], "2.0")
        self.assertTrue(result["new_field"])

    def test_multi_step_migration(self):
        @register_migration("1.0", "2.0")
        def v1_to_v2(data):
            data["schema_version"] = "2.0"
            return data

        @register_migration("2.0", "3.0")
        def v2_to_v3(data):
            data["schema_version"] = "3.0"
            return data

        result = migrate({"schema_version": "1.0"}, "3.0")
        self.assertEqual(result["schema_version"], "3.0")

    def test_missing_version_raises(self):
        with self.assertRaises(SchemaVersionError):
            migrate({"no_version": True}, "1.0")

    def test_no_path_raises(self):
        with self.assertRaises(SchemaVersionError):
            migrate({"schema_version": "1.0"}, "99.0")

    def test_list_migrations_reports_registered_paths(self):
        @register_migration("1.0", "2.0")
        def _v1_to_v2(data):
            data["schema_version"] = "2.0"
            return data

        paths = list_migrations()
        self.assertIn("1.0", paths)
        self.assertIn("2.0", paths["1.0"])
