from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank.coding_agent_workfile import (
    CODING_AGENT_WORKFILE_SCHEMA,
    WORK_STATUS_NEEDS_REVIEW,
    WORK_STATUS_PENDING,
    WORK_STATUS_TRANSCRIBED,
    read_work_file,
    transition_work_status,
    validate_work_file,
    write_work_file,
)


def make_payload() -> dict:
    return {
        "schema": CODING_AGENT_WORKFILE_SCHEMA,
        "questions": [
            {
                "question_number": "1.1",
                "body": "Compute $\\int_0^1 x\\,dx$.",
                "answer": "$\\frac{1}{2}$",
                "explanation": "Apply the fundamental theorem.",
                "work_status": WORK_STATUS_TRANSCRIBED,
            },
            {
                "question_number": "1.2",
                "body": "",
                "answer": "",
                "explanation": "",
                "work_status": WORK_STATUS_PENDING,
            },
        ],
    }


class ValidateWorkFileTests(unittest.TestCase):
    def test_valid_work_file_has_no_findings(self) -> None:
        self.assertEqual([], validate_work_file(make_payload()))

    def test_non_object_payload(self) -> None:
        findings = validate_work_file(["not", "an", "object"])
        self.assertEqual(["work file must be a JSON object"], findings)

    def test_schema_tag_is_enforced(self) -> None:
        payload = make_payload()
        payload["schema"] = "something-else/v9"
        self.assertIn(
            "schema must be 'coding-agent-workfile/v1'",
            validate_work_file(payload)[0],
        )

    def test_empty_questions_list(self) -> None:
        payload = make_payload()
        payload["questions"] = []
        self.assertEqual(
            ["questions must be a non-empty list"],
            validate_work_file(payload),
        )

    def test_duplicate_question_numbers(self) -> None:
        payload = make_payload()
        payload["questions"][1]["question_number"] = "1.1"
        findings = validate_work_file(payload)
        self.assertTrue(any(
            "duplicates question_number '1.1'" in finding for finding in findings
        ))

    def test_unknown_status(self) -> None:
        payload = make_payload()
        payload["questions"][1]["work_status"] = "done"
        self.assertTrue(any(
            "unknown work_status 'done'" in finding
            for finding in validate_work_file(payload)
        ))

    def test_transcribed_requires_body_and_answer(self) -> None:
        payload = make_payload()
        payload["questions"][1]["work_status"] = WORK_STATUS_TRANSCRIBED
        findings = validate_work_file(payload)
        self.assertTrue(any("'body' is empty" in finding for finding in findings))
        self.assertTrue(any("'answer' is empty" in finding for finding in findings))

    def test_needs_review_requires_work_note(self) -> None:
        payload = make_payload()
        payload["questions"][1]["work_status"] = WORK_STATUS_NEEDS_REVIEW
        self.assertTrue(any(
            "no work_note" in finding for finding in validate_work_file(payload)
        ))

    def test_pipeline_owned_fields_are_forbidden(self) -> None:
        payload = make_payload()
        payload["questions"][0]["question_id"] = "KY_SX_SF_AH_2026_4"
        payload["questions"][0]["evidence_sha256"] = "0" * 64
        findings = validate_work_file(payload)
        self.assertTrue(any(
            "pipeline-owned field 'question_id'" in finding for finding in findings
        ))
        self.assertTrue(any(
            "pipeline-owned field 'evidence_sha256'" in finding
            for finding in findings
        ))


class TransitionWorkStatusTests(unittest.TestCase):
    def test_pending_to_transcribed_clears_note(self) -> None:
        payload = make_payload()
        payload["questions"][1]["work_note"] = "page 3 is blurry"
        updated = transition_work_status(payload, "1.2", WORK_STATUS_TRANSCRIBED)
        self.assertEqual(WORK_STATUS_TRANSCRIBED,
                         updated["questions"][1]["work_status"])
        self.assertNotIn("work_note", updated["questions"][1])
        # input is never mutated
        self.assertEqual(WORK_STATUS_PENDING,
                         payload["questions"][1]["work_status"])

    def test_transcribed_to_needs_review_keeps_note(self) -> None:
        payload = transition_work_status(
            make_payload(), "1.1", WORK_STATUS_NEEDS_REVIEW
        )
        payload["questions"][0]["work_note"] = "answer sign uncertain"
        updated = transition_work_status(payload, "1.1", WORK_STATUS_NEEDS_REVIEW)
        self.assertEqual(
            "answer sign uncertain", updated["questions"][0]["work_note"]
        )

    def test_illegal_transition_is_rejected(self) -> None:
        payload = make_payload()
        payload["questions"][1]["work_status"] = WORK_STATUS_NEEDS_REVIEW
        payload["questions"][1]["work_note"] = "check page 2"
        with self.assertRaises(ValueError):
            transition_work_status(payload, "1.2", WORK_STATUS_PENDING)

    def test_unknown_question_number(self) -> None:
        with self.assertRaises(KeyError):
            transition_work_status(make_payload(), "9.9", WORK_STATUS_TRANSCRIBED)


class WorkFileIOTests(unittest.TestCase):
    def test_atomic_round_trip_with_bom(self) -> None:
        payload = make_payload()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nested" / "cards.json"
            write_work_file(path, payload)
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            # simulate an editor adding a BOM
            raw = path.read_bytes()
            path.write_bytes(b"\xef\xbb\xbf" + raw)
            self.assertEqual(payload, read_work_file(path))
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8-sig"))["schema"],
                CODING_AGENT_WORKFILE_SCHEMA,
            )


if __name__ == "__main__":
    unittest.main()

