from __future__ import annotations

import unittest

from dq_questionbank import (
    ImportCandidateSession,
    QuestionSet,
    list_import_cases,
    prepare_import_case,
    validate_with_schema,
)


class PdfTableIntakeTests(unittest.TestCase):
    def test_case_is_installed_and_listed(self):
        summary = next(
            (item for item in list_import_cases() if item.id == "pdf-table"), None
        )

        self.assertIsNotNone(summary)
        self.assertEqual("ai_coding_pdf", summary.route)
        self.assertEqual("pdf", summary.source_type)
        self.assertEqual(
            "pdf-table",
            summary.id,
            "the summary carries the case id used by prepare_import_case",
        )

    def test_prepared_session_carries_structured_blocks_and_evidence(self):
        session = prepare_import_case("pdf-table")
        typed = ImportCandidateSession.from_session(session)

        self.assertEqual("candidate_ready", typed.status)
        self.assertEqual(1, len(typed.candidates))
        candidate = typed.candidates[0]
        self.assertEqual("pdf-table-001", candidate.question_id)
        stem = candidate.question["stem"]["blocks"]
        self.assertEqual("text", stem[0]["type"])
        self.assertEqual("math", stem[1]["type"])
        self.assertIn("\\binom{n}{k}", stem[1]["latex"])
        self.assertEqual("table", stem[3]["type"])
        self.assertEqual(
            [["Outcome", "Count"], ["Success", "3"], ["Failure", "5"]],
            stem[3]["rows"],
        )
        fields = {item["field"] for item in candidate.evidence}
        self.assertEqual({"stem", "answer", "solution"}, fields)
        for item in candidate.evidence:
            self.assertEqual("structured-worksheet.pdf", item["source_path"])
            self.assertTrue(item["locator"])

    def test_review_accepts_and_exports_with_the_table_intact(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("pdf-table"))
        candidate = typed.candidates[0]

        reviewed = typed.decide(
            {
                "decisions": [
                    {
                        "question_id": candidate.question_id,
                        "candidate_sha256": candidate.question_sha256,
                        "decision": "accepted",
                    }
                ]
            }
        )
        exported = reviewed.export_accepted()

        self.assertEqual(1, len(exported.questions))
        blocks = exported.questions[0].stem.blocks
        self.assertEqual("table", blocks[3].type)
        self.assertEqual(
            [["Outcome", "Count"], ["Success", "3"], ["Failure", "5"]], blocks[3].rows
        )
        self.assertEqual("\\sum_{k=0}^{n} \\binom{n}{k} = 2^n", blocks[1].latex)

        round_tripped = QuestionSet.from_dict(exported.to_dict())
        self.assertEqual(exported.to_dict(), round_tripped.to_dict())
        self.assertEqual([], validate_with_schema(exported.to_dict()))

    def test_review_can_reject_without_touching_canonical_data(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("pdf-table"))
        candidate = typed.candidates[0]

        reviewed = typed.decide(
            {
                "decisions": [
                    {
                        "question_id": candidate.question_id,
                        "candidate_sha256": candidate.question_sha256,
                        "decision": "rejected",
                        "note": "Kept out of the canonical set.",
                    }
                ]
            }
        )

        self.assertEqual(1, len(reviewed.rejected))
        self.assertEqual("reviewed", reviewed.status)
        exported = reviewed.export_accepted()
        self.assertEqual(0, len(exported.questions), "rejected content never exports")

    def test_case_source_is_pinned_by_digest_in_the_session(self):
        session = prepare_import_case("pdf-table")

        source = session["source"]
        self.assertEqual("structured-worksheet.pdf", source["path"])
        self.assertEqual(64, len(source["sha256"]))
        self.assertEqual("ai_coding_pdf", session["parser"]["route"])


if __name__ == "__main__":
    unittest.main()
