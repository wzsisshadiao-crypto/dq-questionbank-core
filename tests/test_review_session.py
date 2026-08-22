from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank import (
    ImportBundleError,
    ImportCandidateSession,
    prepare_import_case,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "review-sessions"


def load(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class ReviewSessionContractTests(unittest.TestCase):
    def test_fresh_session_keeps_parser_identity_and_pending_state(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))

        self.assertEqual("canonical-records/1", typed.parser_identity)
        self.assertEqual("manual_web", typed.route)
        self.assertEqual("candidate_ready", typed.status)
        self.assertEqual(1, len(typed.pending))
        self.assertEqual(0, len(typed.accepted))
        self.assertEqual(0, len(typed.rejected))
        self.assertEqual(1, typed.candidates[0].revision)

    def test_dataclass_view_round_trips_the_canonical_document(self):
        session = prepare_import_case("manual-web")
        typed = ImportCandidateSession.from_session(session)

        self.assertEqual(session, typed.to_session())

    def test_tampered_document_fails_closed_at_wrap_time(self):
        session = prepare_import_case("manual-web")
        session["bundle_title"] = "tampered"

        with self.assertRaises(ImportBundleError):
            ImportCandidateSession.from_session(session)

    def test_decision_transitions_are_explicit_and_deterministic(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))
        candidate = typed.candidates[0]

        reviewed = typed.decide(
            {
                "decisions": [
                    {
                        "question_id": candidate.question_id,
                        "candidate_sha256": candidate.question_sha256,
                        "decision": "rejected",
                        "note": "Not wanted.",
                    }
                ]
            }
        )

        self.assertEqual("reviewed", reviewed.status)
        self.assertEqual(1, len(reviewed.rejected))
        self.assertEqual(0, len(reviewed.pending))
        self.assertEqual(candidate.revision, reviewed.candidates[0].revision)

    def test_reviewed_edit_bumps_revision_and_rebinds_digest(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))
        candidate = typed.candidates[0]
        edited = {
            **candidate.question,
            "stem": {
                "blocks": [{"type": "text", "text": "Edited: "}]
                + list(candidate.question["stem"]["blocks"])
            },
        }

        reviewed = typed.decide(
            {
                "decisions": [
                    {
                        "question_id": candidate.question_id,
                        "candidate_sha256": candidate.question_sha256,
                        "decision": "accepted",
                        "edited_question": edited,
                    }
                ]
            }
        )

        self.assertEqual(2, reviewed.candidates[0].revision)
        self.assertNotEqual(
            candidate.question_sha256, reviewed.candidates[0].question_sha256
        )
        self.assertEqual(edited, reviewed.candidates[0].question)

    def test_stale_decision_fails_closed(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))

        with self.assertRaises(ImportBundleError):
            typed.decide(
                {
                    "decisions": [
                        {
                            "question_id": typed.candidates[0].question_id,
                            "candidate_sha256": "0" * 64,
                            "decision": "accepted",
                        }
                    ]
                }
            )

    def test_export_returns_only_accepted_candidates(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))
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
        self.assertEqual(candidate.question_id, exported.questions[0].id)

    def test_export_fails_closed_while_decisions_are_pending(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))

        with self.assertRaises(ImportBundleError):
            typed.export_accepted()


class ReviewSessionFixtureTests(unittest.TestCase):
    def test_pending_fixture_round_trips(self):
        session = load("pending-session.json")

        typed = ImportCandidateSession.from_session(session)

        self.assertEqual(session, typed.to_session())
        self.assertEqual("pending", typed.candidates[0].decision)

    def test_reviewed_fixture_records_accepted_edit_and_revision(self):
        typed = ImportCandidateSession.from_session(load("reviewed-session.json"))

        self.assertEqual("reviewed", typed.status)
        self.assertEqual("accepted", typed.candidates[0].decision)
        self.assertEqual(2, typed.candidates[0].revision)

    def test_rejected_fixture_records_the_rejection_only(self):
        typed = ImportCandidateSession.from_session(load("rejected-session.json"))

        self.assertEqual("reviewed", typed.status)
        self.assertEqual("rejected", typed.candidates[0].decision)
        self.assertEqual(1, typed.candidates[0].revision)

    def test_exported_fixture_matches_export_of_the_reviewed_session(self):
        typed = ImportCandidateSession.from_session(load("reviewed-session.json"))
        exported = load("exported-questions.json")

        self.assertEqual(exported, typed.export_accepted().to_dict())


if __name__ == "__main__":
    unittest.main()
