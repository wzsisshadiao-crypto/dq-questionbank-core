from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank.models import QuestionSet

try:
    import jsonschema
except ImportError:
    jsonschema = None

ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def test_schema_document_is_valid_json_with_expected_identity(self):
        schema = json.loads(
            (ROOT / "schema" / "question-set.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:dq-questionbank:schema:question-set:1.0")
        self.assertIn("question", schema["$defs"])

    def test_sample_uses_only_documented_top_level_properties(self):
        schema = json.loads(
            (ROOT / "schema" / "question-set.schema.json").read_text(encoding="utf-8")
        )
        sample = json.loads(
            (ROOT / "examples" / "sample_questions.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(sample) - set(schema["properties"]), set())
        self.assertEqual(QuestionSet.from_dict(sample).to_dict(), sample)

    def test_content_blocks_and_answers_reject_unknown_properties(self):
        schema = json.loads(
            (ROOT / "schema" / "question-set.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(schema["$defs"]["contentBlock"]["additionalProperties"])
        self.assertFalse(schema["$defs"]["answer"]["additionalProperties"])

    def test_model_does_not_silently_drop_rejected_extension_fields(self):
        sample = json.loads(
            (ROOT / "examples" / "sample_questions.json").read_text(encoding="utf-8")
        )
        sample["questions"][0]["stem"]["blocks"][0]["private_extension"] = True
        with self.assertRaisesRegex(ValueError, "Unknown content block"):
            QuestionSet.from_dict(sample)

    @unittest.skipUnless(jsonschema is not None, "jsonschema is a development dependency")
    def test_sample_validates_against_normative_json_schema(self):
        schema = json.loads(
            (ROOT / "schema" / "question-set.schema.json").read_text(encoding="utf-8")
        )
        sample = json.loads(
            (ROOT / "examples" / "sample_questions.json").read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(sample, schema)
