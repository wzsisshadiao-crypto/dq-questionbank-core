from __future__ import annotations

import unittest

from dq_questionbank.pdf_metadata import (
    PAPER_QUESTION_TYPES,
    PDF_METADATA_SCHEMA,
    PaperMetadataError,
    assert_metadata_matches,
    canonical_paper_metadata,
    metadata_from_questions,
)


def question_row(**overrides: object) -> dict:
    row = {
        "subject": "analysis",
        "question_type": "exam",
        "source": "2026 University A (analysis)",
        "grade": "",
    }
    row.update(overrides)
    return row


class CanonicalPaperMetadataTests(unittest.TestCase):
    def test_valid_metadata_round_trips(self) -> None:
        metadata = canonical_paper_metadata(
            subject="analysis",
            question_type="exam",
            source="2026 University A (analysis)",
        )
        self.assertEqual(PDF_METADATA_SCHEMA, metadata["schema"])
        self.assertEqual("analysis", metadata["subject"])
        self.assertEqual("exam", metadata["question_type"])

    def test_values_are_stripped(self) -> None:
        metadata = canonical_paper_metadata(
            subject="  analysis  ",
            question_type="exam",
            source=" 2026 University A ",
        )
        self.assertEqual("analysis", metadata["subject"])
        self.assertEqual("2026 University A", metadata["source"])

    def test_missing_required_fields_fail_closed(self) -> None:
        with self.assertRaises(PaperMetadataError):
            canonical_paper_metadata(
                subject="", question_type="exam", source="2026 University A"
            )
        with self.assertRaises(PaperMetadataError):
            canonical_paper_metadata(
                subject="analysis", question_type="exam", source=""
            )

    def test_question_type_must_be_in_vocabulary(self) -> None:
        with self.assertRaises(PaperMetadataError):
            canonical_paper_metadata(
                subject="analysis", question_type="whatever", source="2026 A"
            )

    def test_deployments_may_supply_their_own_vocabulary(self) -> None:
        metadata = canonical_paper_metadata(
            subject="analysis",
            question_type="final-exam",
            source="2026 University A",
            allowed_question_types={"final-exam", "mock"},
        )
        self.assertEqual("final-exam", metadata["question_type"])
        self.assertEqual(
            ("exam", "mock", "textbook", "term"), PAPER_QUESTION_TYPES
        )


class MetadataFromQuestionsTests(unittest.TestCase):
    def test_consistent_rows_return_the_shared_metadata(self) -> None:
        rows = [question_row(), question_row(), question_row()]
        metadata = metadata_from_questions(rows)
        self.assertEqual("exam", metadata["question_type"])

    def test_diverging_row_names_the_index(self) -> None:
        rows = [
            question_row(),
            question_row(),
            question_row(source="2025 University B (analysis)"),
        ]
        with self.assertRaises(PaperMetadataError) as caught:
            metadata_from_questions(rows)
        self.assertIn("question index 2", str(caught.exception))

    def test_empty_list_is_rejected(self) -> None:
        with self.assertRaises(PaperMetadataError):
            metadata_from_questions([])


class AssertMetadataMatchesTests(unittest.TestCase):
    def test_matching_blocks_pass(self) -> None:
        expected = canonical_paper_metadata(
            subject="analysis", question_type="exam", source="2026 University A"
        )
        actual = {
            "subject": " analysis ",
            "question_type": "exam",
            "source": "2026 University A",
            "grade": "",
        }
        self.assertEqual(expected, assert_metadata_matches(actual, actual))

    def test_mismatch_raises_with_label(self) -> None:
        with self.assertRaises(PaperMetadataError) as caught:
            assert_metadata_matches(
                {"subject": "algebra", "question_type": "exam",
                 "source": "x", "grade": ""},
                {"subject": "analysis", "question_type": "exam",
                 "source": "x", "grade": ""},
                label="ready/canonical paper metadata",
            )
        self.assertIn("ready/canonical paper metadata", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

