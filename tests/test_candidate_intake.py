from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank.candidate import (
    CandidateQuestion,
    CandidateSession,
    FieldEvidence,
    IntakeImporter,
)
from dq_questionbank.formats.json_format import JsonExporter, JsonImporter
from dq_questionbank.validation import validate_question_set

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "synthetic-intake-candidate.json"
)


class CandidateIntakeTests(unittest.TestCase):
    def test_fixture_file_exists_and_parses(self):
        self.assertTrue(FIXTURE_PATH.is_file())
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["session_id"], "synthetic-intake-session-001")
        self.assertEqual(len(data["candidates"]), 1)

    def test_candidate_records_field_evidence(self):
        session = IntakeImporter().create_session(FIXTURE_PATH)
        candidate = session.get_candidate("cand-pdf-001")
        self.assertIsNotNone(candidate)
        assert candidate is not None

        self.assertIn("stem", candidate.evidence)
        self.assertIn("formula", candidate.evidence)
        self.assertIn("table", candidate.evidence)
        self.assertIn("answer", candidate.evidence)

        stem_ev = candidate.evidence["stem"]
        self.assertEqual(stem_ev.page, 1)
        self.assertIsNotNone(stem_ev.bbox)
        self.assertIn("quadratic function", stem_ev.raw_segment or "")

        table_ev = candidate.evidence["table"]
        self.assertEqual(table_ev.page, 1)
        self.assertIn("x", table_ev.raw_segment or "")

        formula_ev = candidate.evidence["formula"]
        self.assertIn("f(x) =", formula_ev.raw_segment or "")

        answer_ev = candidate.evidence["answer"]
        self.assertIn("4", answer_ev.raw_segment or "")

    def test_review_step_accept_and_reject_without_persistence(self):
        session = IntakeImporter().create_session(FIXTURE_PATH)
        self.assertEqual(len(session.to_question_set().questions), 0)

        session_reject = IntakeImporter().create_session(FIXTURE_PATH)
        session_reject.reject_candidate("cand-pdf-001", reason="Unneeded duplicate")
        candidate_rej = session_reject.get_candidate("cand-pdf-001")
        self.assertIsNotNone(candidate_rej)
        assert candidate_rej is not None
        self.assertEqual(candidate_rej.status, "rejected")
        self.assertEqual(candidate_rej.rejection_reason, "Unneeded duplicate")
        self.assertEqual(len(session_reject.to_question_set().questions), 0)

        session.accept_candidate("cand-pdf-001")
        candidate_acc = session.get_candidate("cand-pdf-001")
        self.assertIsNotNone(candidate_acc)
        assert candidate_acc is not None
        self.assertEqual(candidate_acc.status, "accepted")

        qset = session.to_question_set()
        self.assertEqual(len(qset.questions), 1)

    def test_canonical_structure_and_table_round_trip(self):
        session = IntakeImporter().create_session(FIXTURE_PATH)
        session.accept_candidate("cand-pdf-001")
        question_set = session.to_question_set()

        issues = validate_question_set(question_set)
        self.assertEqual(issues, [])

        question = question_set.questions[0]
        self.assertEqual(question.id, "q-intake-001")
        self.assertEqual(question.type, "short_answer")
        self.assertEqual(question.answer.value if question.answer else None, "4")

        table_blocks = [b for b in question.stem.blocks if b.type == "table"]
        self.assertEqual(len(table_blocks), 1)
        table = table_blocks[0]
        expected_rows = [
            ["x", "f(x)"],
            ["0", "1"],
            ["1", "0"],
            ["2", "1"],
            ["3", "4"],
        ]
        self.assertEqual(table.rows, expected_rows)

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "exported_intake.json"
            JsonExporter().dump(question_set, target)

            imported_set = JsonImporter().load(target)
            self.assertEqual(validate_question_set(imported_set), [])
            self.assertEqual(len(imported_set.questions), 1)

            imp_question = imported_set.questions[0]
            imp_table_blocks = [
                b for b in imp_question.stem.blocks if b.type == "table"
            ]
            self.assertEqual(len(imp_table_blocks), 1)
            self.assertEqual(imp_table_blocks[0].rows, expected_rows)

    def test_candidate_session_serialization_round_trip(self):
        session = IntakeImporter().create_session(FIXTURE_PATH)
        session_dict = session.to_dict()
        reconstructed = CandidateSession.from_dict(session_dict)
        self.assertEqual(reconstructed.session_id, session.session_id)
        self.assertEqual(len(reconstructed.candidates), 1)
        self.assertEqual(reconstructed.candidates[0].candidate_id, "cand-pdf-001")
