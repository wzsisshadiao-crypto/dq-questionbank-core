from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank.import_inbox import (
    BATCH_STATUS_BLOCKED,
    BATCH_STATUS_REGISTERED,
    IMPORT_INBOX_SCHEMA,
    ImportInboxError,
    batch_manifest_digest,
    register_batch,
    validate_batch,
    verify_receipt,
)


def make_batch(**overrides: object) -> dict:
    batch = {
        "schema": IMPORT_INBOX_SCHEMA,
        "batch_id": "AH_2026_JOB",
        "source": "2026 University A (analysis)",
        "questions": [{"file": "q01.json"}, {"file": "q02.json"}],
    }
    batch.update(overrides)
    return batch


def make_question(number: int, **overrides: object) -> dict:
    payload = {
        "question_number": f"{number:02d}",
        "question_id": f"paper-2026-{number}",
        "source": "2026 University A (analysis)",
    }
    payload.update(overrides)
    return payload


def stage(tmp: str, questions: dict[str, dict]) -> Path:
    root = Path(tmp) / "questions"
    root.mkdir(parents=True, exist_ok=True)
    for name, payload in questions.items():
        (root / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return root


class ValidateBatchTests(unittest.TestCase):
    def test_valid_batch_has_no_findings(self) -> None:
        self.assertEqual([], validate_batch(make_batch()))

    def test_bad_batch_id_blocked(self) -> None:
        findings = validate_batch(make_batch(batch_id="bad id!"))
        self.assertTrue(any("batch_id" in f for f in findings))

    def test_missing_source_blocked(self) -> None:
        findings = validate_batch(make_batch(source="  "))
        self.assertTrue(any("source" in f for f in findings))

    def test_bad_file_name_and_duplicates(self) -> None:
        batch = make_batch(questions=[
            {"file": "notes.txt"}, {"file": "q01.json"}, {"file": "q01.json"},
        ])
        findings = validate_batch(batch)
        self.assertTrue(any("must match qNN.json" in f for f in findings))
        self.assertTrue(any("duplicates" in f for f in findings))

    def test_unknown_verdict_rejected(self) -> None:
        batch = make_batch(verdicts={"q01.json": "maybe"})
        findings = validate_batch(batch)
        self.assertTrue(any("maybe" in f for f in findings))

    def test_verdict_for_unknown_file_rejected(self) -> None:
        batch = make_batch(verdicts={"q09.json": "passed"})
        self.assertTrue(any("unknown file" in f for f in validate_batch(batch)))


class RegisterBatchTests(unittest.TestCase):
    def test_clean_delivery_registers_with_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            questions = stage(tmp, {"q01.json": make_question(1),
                                    "q02.json": make_question(2)})
            record = register_batch(make_batch(), questions)
            self.assertEqual(BATCH_STATUS_REGISTERED, record["status"])
            self.assertEqual(2, record["question_count"])
            self.assertEqual([], record["findings"])
            self.assertRegex(record["manifest_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(record["confirmation_digest"], r"^[0-9a-f]{64}$")

    def test_missing_declared_file_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            questions = stage(tmp, {"q01.json": make_question(1)})
            record = register_batch(make_batch(), questions)
            self.assertEqual(BATCH_STATUS_BLOCKED, record["status"])
            self.assertTrue(any("missing on disk" in f for f in record["findings"]))
            self.assertEqual("", record["confirmation_digest"])

    def test_undeclared_extra_file_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            questions = stage(tmp, {
                "q01.json": make_question(1),
                "q02.json": make_question(2),
                "q03.json": make_question(3),
            })
            record = register_batch(make_batch(), questions)
            self.assertEqual(BATCH_STATUS_BLOCKED, record["status"])
            self.assertTrue(any("undeclared" in f for f in record["findings"]))


class ReceiptVerificationTests(unittest.TestCase):
    def test_unchanged_questions_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            questions = stage(tmp, {"q01.json": make_question(1),
                                    "q02.json": make_question(2)})
            record = register_batch(make_batch(), questions)
            receipt = verify_receipt(record, questions)
            self.assertTrue(receipt["verified"])
            self.assertEqual(
                record["confirmation_digest"], receipt["confirmation_digest"]
            )

    def test_post_registration_edit_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            questions = stage(tmp, {"q01.json": make_question(1),
                                    "q02.json": make_question(2)})
            record = register_batch(make_batch(), questions)
            payload = make_question(1, body="edited after registration")
            (questions / "q01.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            receipt = verify_receipt(record, questions)
            self.assertFalse(receipt["verified"])
            self.assertIn("changed after registration", receipt["reason"])

    def test_blocked_batch_cannot_be_verified(self) -> None:
        with self.assertRaises(ImportInboxError):
            verify_receipt({"status": BATCH_STATUS_BLOCKED}, ".")

    def test_manifest_digest_is_content_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            questions = stage(tmp, {"q01.json": make_question(1),
                                    "q02.json": make_question(2)})
            first = batch_manifest_digest(questions)
            payload = make_question(2, body="different")
            (questions / "q02.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            self.assertNotEqual(first, batch_manifest_digest(questions))


if __name__ == "__main__":
    unittest.main()

