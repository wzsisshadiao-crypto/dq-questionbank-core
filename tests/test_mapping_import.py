from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank import (
    FieldMapping,
    QuestionSet,
    apply_mapping,
    load_mapping,
    validate_with_schema,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class FieldMappingTests(unittest.TestCase):
    def test_example_mapping_loads_with_documented_alternates(self):
        mapping = load_mapping(EXAMPLES / "question_mapping.json")

        self.assertEqual("training-exam", mapping.set_id)
        self.assertEqual("stem", mapping.canonical_field_for("Prompt"))
        self.assertEqual("stem", mapping.canonical_field_for("Question"))
        self.assertEqual("analysis", mapping.canonical_field_for("Explanation"))
        self.assertEqual("analysis", mapping.canonical_field_for("Rationale"))
        self.assertIsNone(mapping.canonical_field_for("Difficulty"))

    def test_invalid_targets_and_duplicate_sources_fail_closed(self):
        with self.assertRaises(ValueError):
            FieldMapping.from_dict(
                {"labels": [{"source": "X", "canonical": "not-a-field"}]}
            )
        with self.assertRaises(ValueError):
            FieldMapping.from_dict(
                {
                    "labels": [
                        {"source": "X", "canonical": "stem"},
                        {"source": "X", "canonical": "answer"},
                    ]
                }
            )
        with self.assertRaises(ValueError):
            FieldMapping.from_dict({"labels": [], "surprise": True})

    def test_mapping_round_trips_through_serialization(self):
        mapping = load_mapping(EXAMPLES / "question_mapping.json")

        restored = FieldMapping.from_dict(
            json.loads(json.dumps(mapping.to_dict()))
        )

        self.assertEqual(mapping, restored)


class ApplyMappingTests(unittest.TestCase):
    def test_mapped_fixture_equals_the_hand_written_canonical_json(self):
        mapping = load_mapping(EXAMPLES / "question_mapping.json")
        records = json.loads(
            (EXAMPLES / "mapped_source_records.json").read_text(encoding="utf-8")
        )

        result = apply_mapping(mapping, records)

        self.assertEqual([], result["unmapped_records"])
        self.assertEqual(
            [{"record": 1, "labels": ["Difficulty"]}],
            result["unmapped_labels"],
            "unmapped content is reported, never silently discarded",
        )
        question_set = result["question_set"]
        self.assertEqual([], validate_with_schema(question_set))
        hand_written = {
            "schema_version": "1.0",
            "id": "training-exam",
            "title": "Training exam (mapped)",
            "language": "en",
            "questions": [
                {
                    "schema_version": "1.0",
                    "id": "q-training-exam-1",
                    "type": "single_choice",
                    "language": "en",
                    "stem": {
                        "blocks": [
                            {"type": "text", "text": "Which number is prime?"}
                        ]
                    },
                    "choices": [
                        {
                            "id": "A",
                            "content": {"blocks": [{"type": "text", "text": "4"}]},
                        },
                        {
                            "id": "B",
                            "content": {"blocks": [{"type": "text", "text": "7"}]},
                        },
                        {
                            "id": "C",
                            "content": {"blocks": [{"type": "text", "text": "9"}]},
                        },
                    ],
                    "answer": {"kind": "text", "value": "B"},
                    "metadata": {"analysis": "Only 7 has no divisors other than 1 and itself."},
                    "subject": "Number theory",
                },
                {
                    "schema_version": "1.0",
                    "id": "q-training-exam-2",
                    "type": "short_answer",
                    "language": "en",
                    "stem": {
                        "blocks": [
                            {"type": "text", "text": "State the sum of two and three."}
                        ]
                    },
                    "answer": {"kind": "text", "value": ""},
                    "metadata": {"analysis": "Two plus three equals five."},
                    "solution": {"blocks": [{"type": "text", "text": "2 + 3 = 5."}]},
                },
            ],
        }
        self.assertEqual(hand_written, question_set)
        self.assertEqual(
            hand_written, QuestionSet.from_dict(question_set).to_dict()
        )

    def test_records_without_a_mapped_stem_are_reported(self):
        mapping = FieldMapping(labels=(("Prompt", "stem"),))
        result = apply_mapping(mapping, [{"Completely unknown": "x"}])

        self.assertEqual([0], result["unmapped_records"])
        self.assertEqual([], result["question_set"]["questions"])
        self.assertEqual(
            [{"record": 0, "labels": ["Completely unknown"]}],
            result["unmapped_labels"],
        )


if __name__ == "__main__":
    unittest.main()
