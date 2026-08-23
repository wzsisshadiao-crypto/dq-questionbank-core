from __future__ import annotations

import copy
import unittest

from dq_questionbank import (
    ImportCandidateSession,
    Question,
    QuestionSet,
    detect_quality_findings,
    finding_state,
    prepare_import_case,
    validate_with_schema,
)


def lifecycle_question():
    """Load the pdf-table candidate and accept it into canonical form."""
    typed = ImportCandidateSession.from_session(prepare_import_case("pdf-table"))
    candidate = typed.candidates[0]
    return typed, candidate


class QuestionLifecycleTests(unittest.TestCase):
    def test_full_lifecycle_from_intake_to_reloadable_export(self):
        typed, candidate = lifecycle_question()

        # 1. The question starts as a review candidate, not canonical data.
        self.assertEqual("candidate_ready", typed.status)
        self.assertEqual("pending", candidate.decision)

        # 2. Review accepts the candidate with a field edit (revision bump).
        edited_question = copy.deepcopy(candidate.question)
        edited_question["stem"]["blocks"][0]["text"] = (
            "The table below lists the outcomes of one synthetic trial. Using the identity "
        )
        reviewed = typed.decide(
            {
                "decisions": [
                    {
                        "question_id": candidate.question_id,
                        "candidate_sha256": candidate.question_sha256,
                        "decision": "accepted",
                        "edited_question": edited_question,
                        "note": "Editor Center clarified the stem during review.",
                    }
                ]
            }
        )
        self.assertEqual(2, reviewed.candidates[0].revision)
        exported = reviewed.export_accepted()
        self.assertEqual(1, len(exported.questions))

        # 3. A deterministic quality check runs against the edited question;
        #    a failed check names the affected field and stays editable.
        question = exported.questions[0]
        self.assertEqual([], detect_quality_findings(question))
        broken = Question.from_dict(
            {
                **question.to_dict(),
                "stem": {
                    "blocks": [
                        {"type": "text", "text": "Consider the interval "},
                        {"type": "math", "latex": "(x+1]"},
                    ]
                },
            }
        )
        findings = detect_quality_findings(broken)
        self.assertEqual(1, len(findings))
        self.assertEqual("stem.blocks[1]", findings[0].target_field)
        self.assertEqual("current", finding_state(findings[0], broken))
        repaired_blocks = copy.deepcopy(broken.to_dict()["stem"]["blocks"])
        repaired_blocks[1]["latex"] = "(x+1)"
        repaired = Question.from_dict(
            {**broken.to_dict(), "stem": {"blocks": repaired_blocks}}
        )
        self.assertEqual([], detect_quality_findings(repaired))

        # 4. The exported result reloads without losing formulas or tables.
        payload = exported.to_dict()
        reloaded = QuestionSet.from_dict(payload)
        self.assertEqual(payload, reloaded.to_dict())
        self.assertEqual([], validate_with_schema(payload))
        blocks = reloaded.questions[0].stem.blocks
        self.assertEqual("math", blocks[1].type)
        self.assertIn("\\binom{n}{k}", blocks[1].latex)
        self.assertEqual("table", blocks[3].type)
        self.assertEqual([["Outcome", "Count"], ["Success", "3"], ["Failure", "5"]], blocks[3].rows)

    def test_lifecycle_needs_no_private_application_or_network(self):
        typed, _ = lifecycle_question()

        self.assertEqual("structured-worksheet.pdf", typed.to_session()["source"]["path"])
        self.assertEqual("pdf-table", typed.to_session()["bundle_id"])
        self.assertEqual("canonical-records/1", typed.parser_identity)


if __name__ == "__main__":
    unittest.main()
