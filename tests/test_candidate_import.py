from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dq_questionbank.candidate import IntakeCandidateImporter
from dq_questionbank.formats.json_format import JsonExporter, JsonImporter
from dq_questionbank.formats.markdown import MarkdownExporter, MarkdownImporter
from dq_questionbank.validation import validate_question_set

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "examples" / "synthetic_pdf_table_intake.json"


class CandidateImportTests(unittest.TestCase):
    def test_fixture_contains_question_table_formula_and_answer(self):
        importer = IntakeCandidateImporter()
        session = importer.load_session(FIXTURE_PATH)
        self.assertEqual(session.session_id, "pdf-intake-session-001")
        self.assertEqual(len(session.candidates), 1)

        candidate = session.candidates[0]
        self.assertEqual(candidate.candidate_id, "cand-pdf-math-001")
        self.assertEqual(candidate.status, "pending")

        self.assertIn("stem", candidate.extracted_fields)
        self.assertIn("table", candidate.extracted_fields)
        self.assertIn("answer", candidate.extracted_fields)

        stem_val = candidate.extracted_fields["stem"].value
        self.assertEqual(stem_val["latex_formula"], "f(x) = x^2 + 3x")

        table_val = candidate.extracted_fields["table"].value
        self.assertEqual(
            table_val["rows"],
            [["x", "f(x)"], ["1", "4"], ["2", "10"], ["3", "18"]],
        )

        answer_val = candidate.extracted_fields["answer"].value
        self.assertEqual(answer_val["value"], "18")

    def test_candidate_records_field_source_evidence(self):
        importer = IntakeCandidateImporter()
        session = importer.load_session(FIXTURE_PATH)
        candidate = session.get_candidate("cand-pdf-math-001")
        self.assertIsNotNone(candidate)

        stem_evidence = candidate.get_field_evidence("stem")
        self.assertIsNotNone(stem_evidence)
        self.assertEqual(stem_evidence.source_locator, "page 3, lines 1-3")
        self.assertEqual(stem_evidence.confidence, 0.98)

        table_evidence = candidate.get_field_evidence("table")
        self.assertIsNotNone(table_evidence)
        self.assertEqual(table_evidence.source_locator, "page 3, table_block_1")

        answer_evidence = candidate.get_field_evidence("answer")
        self.assertIsNotNone(answer_evidence)
        self.assertEqual(answer_evidence.source_locator, "page 3, line 12")

    def test_review_step_accept_or_reject_without_side_effects(self):
        importer = IntakeCandidateImporter()

        session_reject = importer.load_session(FIXTURE_PATH)
        session_reject.review_candidate("cand-pdf-math-001", "rejected", reviewer_notes="Low quality")
        candidate = session_reject.get_candidate("cand-pdf-math-001")
        self.assertEqual(candidate.status, "rejected")
        self.assertEqual(candidate.reviewer_notes, "Low quality")

        qs_rejected = session_reject.to_question_set("rejected-set")
        self.assertEqual(len(qs_rejected.questions), 0)

        session_accept = importer.load_session(FIXTURE_PATH)
        session_accept.review_candidate("cand-pdf-math-001", "accepted")
        qs_accepted = session_accept.to_question_set("accepted-set", "Accepted Questions")
        self.assertEqual(len(qs_accepted.questions), 1)
        self.assertEqual(qs_accepted.questions[0].id, "cand-pdf-math-001")

        issues = validate_question_set(qs_accepted)
        self.assertEqual(issues, [])

    def test_canonical_structure_and_table_round_trip(self):
        importer = IntakeCandidateImporter()
        session = importer.load_session(FIXTURE_PATH)
        session.review_candidate("cand-pdf-math-001", "accepted")
        qs = session.to_question_set()

        question = qs.questions[0]
        self.assertEqual(question.id, "cand-pdf-math-001")
        self.assertEqual(question.type, "short_answer")
        self.assertEqual(question.answer.value, "18")

        block_types = [b.type for b in question.stem.blocks]
        self.assertIn("text", block_types)
        self.assertIn("math", block_types)
        self.assertIn("table", block_types)

        table_block = next(b for b in question.stem.blocks if b.type == "table")
        self.assertEqual(
            table_block.rows,
            [["x", "f(x)"], ["1", "4"], ["2", "10"], ["3", "18"]],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            json_path = tmp_path / "candidate.json"
            JsonExporter().dump(qs, json_path)
            qs_reloaded = JsonImporter().load(json_path)
            self.assertEqual(qs.to_dict(), qs_reloaded.to_dict())

            md_path = tmp_path / "candidate.md"
            MarkdownExporter().dump(qs, md_path)
            md_text = md_path.read_text(encoding="utf-8")

            self.assertIn("x | f(x)", md_text)
            self.assertIn("1 | 4", md_text)
            self.assertIn("2 | 10", md_text)
            self.assertIn("3 | 18", md_text)
            self.assertIn("$f(x) = x^2 + 3x$", md_text)

            qs_md_reloaded = MarkdownImporter().load(md_path)
            self.assertEqual(len(qs_md_reloaded.questions), 1)
            reloaded_q = qs_md_reloaded.questions[0]
            reloaded_table = next(b for b in reloaded_q.stem.blocks if b.type == "table")
            self.assertEqual(
                reloaded_table.rows,
                [["x", "f(x)"], ["1", "4"], ["2", "10"], ["3", "18"]],
            )
