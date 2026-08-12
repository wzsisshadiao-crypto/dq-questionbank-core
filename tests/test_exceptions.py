"""Tests for the exception hierarchy and unified validation pipeline."""

from __future__ import annotations

import unittest

from dq_questionbank.exceptions import (
    FormatDetectionError,
    FormatError,
    FormatLoadError,
    FormatWriteError,
    QuestionBankError,
    SchemaError,
    SchemaNotFoundError,
    SchemaValidationError,
    SchemaVersionError,
)
from dq_questionbank.validation import validate_with_schema


class ExceptionHierarchyTests(unittest.TestCase):
    def test_all_exceptions_are_catchable_via_base(self):
        for cls in (
            FormatDetectionError,
            FormatLoadError,
            FormatWriteError,
            SchemaNotFoundError,
            SchemaValidationError,
            SchemaVersionError,
        ):
            with self.subTest(cls=cls):
                self.assertTrue(issubclass(cls, QuestionBankError))
                self.assertIsInstance(cls("msg"), QuestionBankError)

    def test_format_errors_share_base(self):
        self.assertTrue(issubclass(FormatDetectionError, FormatError))
        self.assertTrue(issubclass(FormatLoadError, FormatError))
        self.assertTrue(issubclass(FormatWriteError, FormatError))

    def test_schema_errors_share_base(self):
        self.assertTrue(issubclass(SchemaNotFoundError, SchemaError))
        self.assertTrue(issubclass(SchemaValidationError, SchemaError))
        self.assertTrue(issubclass(SchemaVersionError, SchemaError))

    def test_format_detection_is_precise(self):
        with self.assertRaises(FormatDetectionError) as ctx:
            raise FormatDetectionError("Cannot detect")
        self.assertIn("Cannot detect", str(ctx.exception))
        self.assertIsInstance(ctx.exception, FormatError)


class UnifiedValidationTests(unittest.TestCase):
    def test_valid_payload_passes_both_schema_and_semantic(self):
        payload = {
            "schema_version": "1.0",
            "id": "test-set",
            "title": "Test Set",
            "language": "en",
            "questions": [
                {
                    "schema_version": "1.0",
                    "id": "q1",
                    "type": "short_answer",
                    "language": "en",
                    "stem": {"blocks": [{"type": "text", "text": "What is 2+2?"}]},
                }
            ],
        }
        issues = validate_with_schema(payload)
        self.assertEqual(issues, [])

    def test_invalid_schema_version_is_reported(self):
        payload = {
            "schema_version": "99.99",
            "id": "test-set",
            "title": "Test Set",
            "language": "en",
            "questions": [],
        }
        issues = validate_with_schema(payload)
        self.assertTrue(any("unsupported_schema" in str(i) for i in issues))
