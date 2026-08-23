from __future__ import annotations

import unittest

from dq_questionbank import ImportBundleError, ImportCandidateSession, prepare_import_case
from dq_questionbank.acceptance_report import (
    AcceptanceReport,
    build_acceptance_report,
    render_markdown_table,
)


def accept_all(case_id: str) -> dict:
    """Prepare a case and accept every candidate through the public API."""
    typed = ImportCandidateSession.from_session(prepare_import_case(case_id))
    return typed.decide(
        {
            "decisions": [
                {
                    "question_id": candidate.question_id,
                    "candidate_sha256": candidate.question_sha256,
                    "decision": "accepted",
                }
                for candidate in typed.candidates
            ]
        }
    ).to_session()


class AcceptanceReportTests(unittest.TestCase):
    def test_manual_web_route_counts_decisions(self):
        report = build_acceptance_report(accept_all("manual-web"))

        self.assertEqual("manual_web", report.route)
        self.assertEqual(1, report.candidates)
        self.assertEqual({"accepted": 1, "rejected": 0, "pending": 0}, dict(report.totals))
        self.assertEqual(0, report.edited_candidates)

    def test_pdf_table_route_counts_rule_ids_from_diagnostics(self):
        report = build_acceptance_report(accept_all("pdf-table"))

        counts = dict(report.rule_counts)
        self.assertEqual(1, counts.get("unmapped_source_field"))
        self.assertTrue(all(isinstance(rule, str) and rule for rule in counts))

    def test_omml_route_reports_bundle_and_candidates(self):
        report = build_acceptance_report(accept_all("coding-exam-omml"))

        self.assertTrue(report.bundle_id)
        self.assertGreaterEqual(report.candidates, 1)
        self.assertEqual(report.candidates, sum(count for _, count in report.totals))

    def test_rejected_decisions_are_totalled(self):
        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))
        candidate = typed.candidates[0]
        reviewed = typed.decide(
            {
                "decisions": [
                    {
                        "question_id": candidate.question_id,
                        "candidate_sha256": candidate.question_sha256,
                        "decision": "rejected",
                    }
                ]
            }
        ).to_session()

        report = build_acceptance_report(reviewed)

        self.assertEqual({"accepted": 0, "rejected": 1, "pending": 0}, dict(report.totals))

    def test_pending_session_reports_pending_counts(self):
        report = build_acceptance_report(prepare_import_case("manual-web"))

        self.assertEqual({"accepted": 0, "rejected": 0, "pending": 1}, dict(report.totals))

    def test_edited_candidates_are_counted(self):
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
        ).to_session()

        report = build_acceptance_report(reviewed)

        self.assertEqual(1, report.edited_candidates)

    def test_tampered_session_fails_closed(self):
        session = prepare_import_case("manual-web")
        session["bundle_title"] = "tampered"

        with self.assertRaises(ImportBundleError):
            build_acceptance_report(session)

    def test_markdown_renderer_is_deterministic_and_complete(self):
        session = accept_all("pdf-table")
        report = build_acceptance_report(session)

        table = render_markdown_table(report)

        self.assertEqual(table, render_markdown_table(build_acceptance_report(session)))
        self.assertIn("| unmapped_source_field | 1 |", table)
        self.assertIn("accepted 1", table)


class AcceptanceReportSerializationTests(unittest.TestCase):
    def test_round_trip(self):
        report = build_acceptance_report(accept_all("pdf-table"))

        restored = AcceptanceReport.from_dict(report.to_dict())

        self.assertEqual(report, restored)

    def test_from_dict_rejects_unknown_keys(self):
        payload = build_acceptance_report(accept_all("manual-web")).to_dict()
        payload["extra"] = 1

        with self.assertRaises(ValueError):
            AcceptanceReport.from_dict(payload)

    def test_from_dict_rejects_wrong_version(self):
        payload = build_acceptance_report(accept_all("manual-web")).to_dict()
        payload["report_version"] = "acceptance-report/999"

        with self.assertRaises(ValueError):
            AcceptanceReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
