from __future__ import annotations

import unittest

from dq_questionbank.models import Content, ContentBlock, Question
from dq_questionbank.subpart_structure import (
    SUBPART_VERSION,
    SubpartInference,
    infer_subparts,
)


def _text_stem(*values: str) -> Content:
    return Content([ContentBlock(type="text", text=value) for value in values])


class SubpartSplitTests(unittest.TestCase):
    def test_clean_numbering_across_blocks_splits_three_subquestions(self):
        stem = _text_stem(
            "(1) Compute the area of the first square.",
            "(2) Compute the area of the second square.",
            "(3) Explain why the two areas differ.",
        )
        result = infer_subparts(stem, base_id="q-42")
        self.assertTrue(result.changed)
        self.assertEqual(result.reasons, ())
        self.assertEqual(
            [item["id"] for item in result.subquestions],
            ["q-42-p1", "q-42-p2", "q-42-p3"],
        )
        for item in result.subquestions:
            self.assertEqual(
                sorted(item),
                ["id", "language", "schema_version", "stem", "type"],
            )
            self.assertEqual(item["type"], "short_answer")
            self.assertEqual(item["language"], "en")
            self.assertEqual(Question.from_dict(item).to_dict(), item)

    def test_empty_base_id_yields_bare_part_ids(self):
        result = infer_subparts(_text_stem("(1) One.", "(2) Two."))
        self.assertEqual([item["id"] for item in result.subquestions], ["p1", "p2"])

    def test_single_run_numbering_splits_inside_one_block(self):
        result = infer_subparts(_text_stem("Answer both. (1) One. (2) Two."))
        self.assertTrue(result.changed)
        self.assertEqual(
            result.subquestions[0]["stem"]["blocks"],
            [{"type": "text", "text": "(1) One. "}],
        )
        self.assertEqual(
            result.subquestions[1]["stem"]["blocks"],
            [{"type": "text", "text": "(2) Two."}],
        )

    def test_leading_context_blocks_stay_with_the_parent_stem(self):
        stem = _text_stem("Read the passage carefully.", "(1) First.", "(2) Second.")
        result = infer_subparts(stem, base_id="q7")
        self.assertTrue(result.changed)
        self.assertEqual(len(result.subquestions), 2)
        self.assertEqual(
            result.subquestions[0]["stem"]["blocks"][0]["text"], "(1) First."
        )

    def test_math_blocks_attach_to_the_preceding_subpart(self):
        stem = Content(
            [
                ContentBlock(type="text", text="(1) Solve the equation."),
                ContentBlock(type="math", latex="x+1=2"),
                ContentBlock(type="text", text="(2) Explain the result."),
            ]
        )
        result = infer_subparts(stem, base_id="q8")
        self.assertTrue(result.changed)
        self.assertEqual(
            result.subquestions[0]["stem"]["blocks"],
            [
                {"type": "text", "text": "(1) Solve the equation."},
                {"type": "math", "latex": "x+1=2"},
            ],
        )

    def test_input_stem_is_never_mutated(self):
        stem = _text_stem("(1) One.", "(2) Two.")
        before = stem.to_dict()
        result = infer_subparts(stem, base_id="q9")
        self.assertTrue(result.changed)
        self.assertEqual(stem.to_dict(), before)


class SubpartRefusalTests(unittest.TestCase):
    def test_nested_parens_reference_is_not_a_marker(self):
        result = infer_subparts(
            _text_stem("Recall the setup (see part (1) above) before answering.")
        )
        self.assertFalse(result.changed)
        self.assertEqual(result.subquestions, ())
        self.assertIn("no-numbering", result.reasons)

    def test_roman_numeral_numbering_is_refused(self):
        result = infer_subparts(_text_stem("(i) First task.", "(ii) Second task."))
        self.assertFalse(result.changed)
        self.assertIn("non-arabic-numbering", result.reasons)

    def test_letter_numbering_is_refused(self):
        result = infer_subparts(_text_stem("(a) First task.", "(b) Second task."))
        self.assertFalse(result.changed)
        self.assertIn("non-arabic-numbering", result.reasons)

    def test_missing_number_is_refused(self):
        result = infer_subparts(_text_stem("(1) First task.", "(3) Third task."))
        self.assertFalse(result.changed)
        self.assertIn("non-monotonic-numbering", result.reasons)

    def test_out_of_order_numbering_is_refused(self):
        result = infer_subparts(_text_stem("(2) Second task.", "(1) First task."))
        self.assertFalse(result.changed)
        self.assertIn("non-monotonic-numbering", result.reasons)

    def test_empty_stem_is_unchanged(self):
        result = infer_subparts(Content())
        self.assertFalse(result.changed)
        self.assertEqual(result.subquestions, ())
        self.assertIn("empty-stem", result.reasons)

    def test_numbering_inside_math_blocks_is_never_considered(self):
        stem = Content(
            [
                ContentBlock(type="text", text="Solve the following equations."),
                ContentBlock(type="math", latex="(1) x + 1 = 2"),
                ContentBlock(type="math", latex="(2) x - 1 = 0"),
            ]
        )
        result = infer_subparts(stem)
        self.assertFalse(result.changed)
        self.assertIn("no-numbering", result.reasons)

    def test_trailing_unnumbered_text_block_is_refused(self):
        result = infer_subparts(
            _text_stem("(1) First.", "(2) Second.", "Now check your work.")
        )
        self.assertFalse(result.changed)
        self.assertIn("trailing-unnumbered-content", result.reasons)

    def test_single_marker_is_insufficient(self):
        result = infer_subparts(_text_stem("(1) Only one numbered part here."))
        self.assertFalse(result.changed)
        self.assertIn("insufficient-numbering", result.reasons)


class SubpartSerializationTests(unittest.TestCase):
    def test_round_trip_is_lossless(self):
        result = infer_subparts(_text_stem("(1) One.", "(2) Two."), base_id="q1")
        self.assertEqual(SubpartInference.from_dict(result.to_dict()), result)

    def test_refusal_round_trip_is_lossless(self):
        result = infer_subparts(Content())
        self.assertEqual(SubpartInference.from_dict(result.to_dict()), result)

    def test_from_dict_rejects_unknown_fields(self):
        result = infer_subparts(Content())
        payload = result.to_dict()
        payload["note"] = "extra"
        with self.assertRaises(ValueError):
            SubpartInference.from_dict(payload)

    def test_version_is_stable(self):
        self.assertEqual(SUBPART_VERSION, "subpart/1")


if __name__ == "__main__":
    unittest.main()

