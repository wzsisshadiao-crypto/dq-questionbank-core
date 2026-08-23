from __future__ import annotations

import unittest

from dq_questionbank.import_preflight import (
    CLASS_DUPLICATE,
    CLASS_LIKELY,
    CLASS_UNIQUE,
    PreflightReport,
    document_profile,
    preflight,
    question_fingerprint,
)
from dq_questionbank.models import Content, ContentBlock, Question, QuestionSet

BASE_TEXT = (
    "A synthetic train travels between two stations and the timetable "
    "lists the distances travelled each hour of the journey."
)


def make_question(
    question_id: str,
    text: str = BASE_TEXT,
    extra_blocks: list[ContentBlock] | None = None,
) -> Question:
    """Build a synthetic single-text question with optional extra blocks."""
    blocks = [ContentBlock(type="text", text=text)]
    if extra_blocks:
        blocks.extend(extra_blocks)
    return Question(id=question_id, type="short_answer", stem=Content(blocks))


def make_set(*questions: Question) -> QuestionSet:
    return QuestionSet(id="existing", title="Existing", questions=list(questions))


class DuplicatePreflightTests(unittest.TestCase):
    def test_exact_duplicate_is_flagged_with_matched_id(self):
        original = make_question("q-existing")
        candidate = make_question("q-new")

        report = preflight(candidate, make_set(original))

        self.assertEqual(CLASS_DUPLICATE, report.classification)
        self.assertEqual("q-existing", report.matched_question_id)
        self.assertEqual(("fingerprint-match",), report.reasons)

    def test_case_only_difference_is_still_a_duplicate(self):
        original = make_question("q-existing", text="Evaluate the expression below.")
        candidate = make_question("q-new", text="EVALUATE the expression below.")

        report = preflight(candidate, make_set(original))

        self.assertEqual(CLASS_DUPLICATE, report.classification)

    def test_whitespace_run_difference_is_still_a_duplicate(self):
        original = make_question("q-existing", text="Compute   the    total.")
        candidate = make_question("q-new", text=" Compute the  total. ")

        report = preflight(candidate, make_set(original))

        self.assertEqual(CLASS_DUPLICATE, report.classification)

    def test_near_duplicate_with_same_structure_is_likely(self):
        original = make_question("q-existing")
        candidate = make_question("q-new", text=BASE_TEXT + " Ok")  # +3 chars ~= 2%

        report = preflight(candidate, make_set(original))

        self.assertEqual(CLASS_LIKELY, report.classification)
        self.assertEqual("q-existing", report.matched_question_id)
        self.assertEqual(
            (("text_length", str(len(BASE_TEXT) + 3), str(len(BASE_TEXT))),),
            report.profile_diff,
        )

    def test_structurally_different_question_is_unique(self):
        original = make_question("q-existing")
        candidate = make_question(
            "q-new",
            text=BASE_TEXT,
            extra_blocks=[ContentBlock(type="math", latex="\\frac{a}{b}")],
        )

        report = preflight(candidate, make_set(original))

        self.assertEqual(CLASS_UNIQUE, report.classification)
        self.assertIsNone(report.matched_question_id)
        self.assertEqual((), report.profile_diff)

    def test_empty_existing_set_is_unique(self):
        report = preflight(make_question("q-new"), make_set())

        self.assertEqual(CLASS_UNIQUE, report.classification)

    def test_preflight_never_mutates_its_inputs(self):
        original = make_question("q-existing")
        candidate = make_question("q-new")
        before = (original.to_dict(), candidate.to_dict())

        preflight(candidate, make_set(original))

        self.assertEqual(before, (original.to_dict(), candidate.to_dict()))


class PreflightHelperTests(unittest.TestCase):
    def test_fingerprint_is_deterministic_and_content_sensitive(self):
        second = make_question("q1")
        second.stem.blocks[0].text = "Different wording entirely."

        self.assertEqual(
            question_fingerprint(make_question("q1")),
            question_fingerprint(make_question("q1")),
        )
        self.assertNotEqual(
            question_fingerprint(make_question("q1")), question_fingerprint(second)
        )

    def test_document_profile_counts_shape_not_wording(self):
        question = make_question(
            "q1",
            extra_blocks=[
                ContentBlock(type="math", latex="x+1"),
                ContentBlock(type="table", rows=[["a", "b"]]),
            ],
        )

        profile = document_profile(question)

        self.assertEqual(
            {
                "block_count": 3,
                "block_types": {"math": 1, "table": 1, "text": 1},
                "text_length": len(BASE_TEXT),
                "math_count": 1,
                "table_count": 1,
                "choice_count": 0,
            },
            profile,
        )


class PreflightReportSerializationTests(unittest.TestCase):
    def test_round_trip(self):
        report = preflight(
            make_question("q-new", text=BASE_TEXT + " Ok"), make_set(make_question("q-existing"))
        )

        restored = PreflightReport.from_dict(report.to_dict())

        self.assertEqual(report, restored)

    def test_from_dict_rejects_unknown_keys(self):
        payload = preflight(make_question("q-new"), make_set()).to_dict()
        payload["extra"] = 1

        with self.assertRaises(ValueError):
            PreflightReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
