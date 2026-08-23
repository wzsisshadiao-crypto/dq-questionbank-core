from __future__ import annotations

import unittest

from dq_questionbank.bilingual_splitter import (
    BILINGUAL_SPLIT_VERSION,
    SUPPORTED_LANGUAGES,
    BilingualSplit,
    split_bilingual_stem,
)
from dq_questionbank.models import Content, ContentBlock, Question, QuestionSet
from dq_questionbank.passage_splitter import (
    PASSAGE_SPLIT_VERSION,
    PassageSplit,
    split_shared_passage,
)


def _question(question_id: str, texts: list[str]) -> Question:
    return Question(
        id=question_id,
        type="short_answer",
        stem=Content([ContentBlock(type="text", text=value) for value in texts]),
    )


def _question_set(*questions: Question) -> QuestionSet:
    return QuestionSet(id="set-1", title="Synthetic set", questions=list(questions))


PASSAGE_ONE = "The northern road was closed after the storm."
PASSAGE_TWO = "Travellers had to use the ferry instead."


class SharedPassageTests(unittest.TestCase):
    def test_clean_shared_passage_is_lifted(self):
        question_set = _question_set(
            _question("q1", [PASSAGE_ONE, PASSAGE_TWO, "How long was the road closed?"]),
            _question("q2", [PASSAGE_ONE, PASSAGE_TWO, "Why was the ferry needed?"]),
            _question("q3", [PASSAGE_ONE, PASSAGE_TWO, "Who closed the road?"]),
        )
        result = split_shared_passage(question_set)
        self.assertTrue(result.changed)
        self.assertEqual(result.reasons, ())
        self.assertEqual(
            result.shared_blocks,
            (
                {"type": "text", "text": PASSAGE_ONE},
                {"type": "text", "text": PASSAGE_TWO},
            ),
        )
        self.assertEqual(
            result.question_stems,
            (
                ("q1", ({"type": "text", "text": "How long was the road closed?"},)),
                ("q2", ({"type": "text", "text": "Why was the ferry needed?"},)),
                ("q3", ({"type": "text", "text": "Who closed the road?"},)),
            ),
        )

    def test_partial_overlap_differing_at_block_one_is_unchanged(self):
        question_set = _question_set(
            _question("q1", ["Version one of the passage.", "Shared tail.", "Ask one?"]),
            _question("q2", ["Version two of the passage.", "Shared tail.", "Ask two?"]),
        )
        result = split_shared_passage(question_set)
        self.assertFalse(result.changed)
        self.assertEqual(result.shared_blocks, ())
        self.assertEqual(result.question_stems, ())
        self.assertIn("no-common-prefix", result.reasons)

    def test_single_question_set_is_unchanged(self):
        question_set = _question_set(_question("q1", [PASSAGE_ONE, "Ask one?"]))
        result = split_shared_passage(question_set)
        self.assertFalse(result.changed)
        self.assertIn("single-question", result.reasons)

    def test_question_equal_to_the_prefix_is_unchanged(self):
        question_set = _question_set(
            _question("q1", [PASSAGE_ONE, "Ask one?"]),
            _question("q2", [PASSAGE_ONE]),
        )
        result = split_shared_passage(question_set)
        self.assertFalse(result.changed)
        self.assertIn("empty-remainder", result.reasons)

    def test_input_question_set_is_never_mutated(self):
        question_set = _question_set(
            _question("q1", [PASSAGE_ONE, "Ask one?"]),
            _question("q2", [PASSAGE_ONE, "Ask two?"]),
        )
        before = question_set.to_dict()
        result = split_shared_passage(question_set)
        self.assertTrue(result.changed)
        self.assertEqual(question_set.to_dict(), before)


class SharedPassageSerializationTests(unittest.TestCase):
    def test_round_trip_is_lossless(self):
        question_set = _question_set(
            _question("q1", [PASSAGE_ONE, "Ask one?"]),
            _question("q2", [PASSAGE_ONE, "Ask two?"]),
        )
        result = split_shared_passage(question_set)
        self.assertEqual(PassageSplit.from_dict(result.to_dict()), result)

    def test_from_dict_rejects_unknown_fields(self):
        question_set = _question_set(_question("q1", [PASSAGE_ONE, "Ask one?"]))
        payload = split_shared_passage(question_set).to_dict()
        payload["note"] = "extra"
        with self.assertRaises(ValueError):
            PassageSplit.from_dict(payload)

    def test_version_is_stable(self):
        self.assertEqual(PASSAGE_SPLIT_VERSION, "passage-split/1")


class BilingualSplitTests(unittest.TestCase):
    def test_clean_bilingual_stem_splits_with_math_attached(self):
        stem = Content(
            [
                ContentBlock(type="text", text="Find the area of the rectangle."),
                ContentBlock(type="math", latex="A=lw"),
                ContentBlock(
                    type="text", text="\u6c42\u9634\u5f71\u90e8\u5206\u7684\u9762\u79ef\u3002"
                ),
            ]
        )
        result = split_bilingual_stem(stem)
        self.assertTrue(result.changed)
        self.assertEqual(result.reasons, ())
        self.assertEqual(
            result.segments,
            (
                {
                    "language": "en",
                    "blocks": [
                        {"type": "text", "text": "Find the area of the rectangle."},
                        {"type": "math", "latex": "A=lw"},
                    ],
                },
                {
                    "language": "zh",
                    "blocks": [
                        {
                            "type": "text",
                            "text": "\u6c42\u9634\u5f71\u90e8\u5206\u7684\u9762\u79ef\u3002",
                        }
                    ],
                },
            ),
        )

    def test_single_language_stem_is_unchanged(self):
        result = split_bilingual_stem(
            Content([ContentBlock(type="text", text="Only English here.")])
        )
        self.assertFalse(result.changed)
        self.assertEqual(result.segments, ())
        self.assertIn("single-language", result.reasons)

    def test_chinese_only_stem_is_unchanged(self):
        result = split_bilingual_stem(
            Content([ContentBlock(type="text", text="\u53ea\u6709\u4e2d\u6587\u7684\u9898\u5e72\u3002")])
        )
        self.assertFalse(result.changed)
        self.assertIn("single-language", result.reasons)

    def test_intra_block_mixed_script_is_unchanged(self):
        result = split_bilingual_stem(
            Content(
                [ContentBlock(type="text", text="\u6c42 x \u7684\u503c\u5e76 find the answer.")]
            )
        )
        self.assertFalse(result.changed)
        self.assertEqual(result.segments, ())
        self.assertIn("mixed-script-block", result.reasons)

    def test_empty_stem_is_unchanged(self):
        result = split_bilingual_stem(Content())
        self.assertFalse(result.changed)
        self.assertIn("empty-stem", result.reasons)

    def test_stem_without_text_blocks_is_unchanged(self):
        stem = Content([ContentBlock(type="math", latex="x+1=2")])
        result = split_bilingual_stem(stem)
        self.assertFalse(result.changed)
        self.assertIn("no-text-blocks", result.reasons)

    def test_input_stem_is_never_mutated(self):
        stem = Content(
            [
                ContentBlock(type="text", text="English part."),
                ContentBlock(type="text", text="\u4e2d\u6587\u90e8\u5206\u3002"),
            ]
        )
        before = stem.to_dict()
        result = split_bilingual_stem(stem)
        self.assertTrue(result.changed)
        self.assertEqual(stem.to_dict(), before)


class BilingualSerializationTests(unittest.TestCase):
    def test_round_trip_is_lossless(self):
        stem = Content(
            [
                ContentBlock(type="text", text="English part."),
                ContentBlock(type="text", text="\u4e2d\u6587\u90e8\u5206\u3002"),
            ]
        )
        result = split_bilingual_stem(stem)
        self.assertEqual(BilingualSplit.from_dict(result.to_dict()), result)

    def test_from_dict_rejects_unknown_fields(self):
        payload = split_bilingual_stem(Content()).to_dict()
        payload["note"] = "extra"
        with self.assertRaises(ValueError):
            BilingualSplit.from_dict(payload)

    def test_from_dict_rejects_unsupported_language(self):
        payload = split_bilingual_stem(Content()).to_dict()
        payload["segments"] = [{"language": "fr", "blocks": []}]
        with self.assertRaises(ValueError):
            BilingualSplit.from_dict(payload)

    def test_version_and_languages_are_stable(self):
        self.assertEqual(BILINGUAL_SPLIT_VERSION, "bilingual-split/1")
        self.assertEqual(SUPPORTED_LANGUAGES, ("en", "zh"))


if __name__ == "__main__":
    unittest.main()
