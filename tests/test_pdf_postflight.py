from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank.pdf_postflight import (
    canonical_question_sha256,
    scan_candidate_dir,
)


def make_question(number: int, **overrides: object) -> dict:
    payload = {
        "question_number": f"{number:02d}",
        "question_id": f"KY_SX_SF_AH_2026_{number}",
        "source": "2026 University A (analysis)",
        "body": f"Question {number} body.",
    }
    payload.update(overrides)
    return payload


def stage(tmp: str, questions: dict[str, dict], manifest: dict | None = None) -> Path:
    root = Path(tmp)
    for name, payload in questions.items():
        (root / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if manifest is not None:
        (root / MANIFEST_FILE).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return root


MANIFEST_FILE = "manifest.json"


class ScanCandidateDirTests(unittest.TestCase):
    def test_clean_directory_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            questions = {
                f"q{number:02d}.json": make_question(number) for number in (1, 2, 3)
            }
            root = stage(temporary, questions, {
                "files": {
                    name: canonical_question_sha256(payload)
                    for name, payload in questions.items()
                }
            })
            report = scan_candidate_dir(root)
            self.assertTrue(report["ok"], report["findings"])
            self.assertEqual(3, report["question_count"])
            self.assertEqual(
                ["q01.json", "q02.json", "q03.json"],
                [entry["file"] for entry in report["questions"]],
            )
            self.assertEqual(
                "KY_SX_SF_AH_2026_2", report["questions"][1]["question_id"]
            )

    def test_numbering_gap_is_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = stage(temporary, {
                "q01.json": make_question(1),
                "q03.json": make_question(3),
            })
            report = scan_candidate_dir(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any("gaps" in finding for finding in report["findings"]))
            self.assertTrue(any("q02" in finding for finding in report["findings"]))

    def test_numbering_must_start_at_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = stage(temporary, {"q02.json": make_question(2)})
            report = scan_candidate_dir(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any(
                "starts at 2" in finding for finding in report["findings"]
            ))

    def test_duplicate_numbers_are_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = stage(temporary, {
                "q01.json": make_question(1),
                "q001.json": make_question(1),
            })
            report = scan_candidate_dir(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any(
                "duplicate question number 1" in finding
                for finding in report["findings"]
            ))

    def test_missing_required_field_is_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = stage(temporary, {
                "q01.json": make_question(1, question_id=""),
            })
            report = scan_candidate_dir(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any(
                "missing question_id" in finding for finding in report["findings"]
            ))

    def test_declared_content_hash_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = make_question(1, content_sha256="0" * 64)
            root = stage(temporary, {"q01.json": payload})
            report = scan_candidate_dir(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any(
                "content_sha256 does not match" in finding
                for finding in report["findings"]
            ))

    def test_manifest_mismatch_is_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = stage(temporary, {
                "q01.json": make_question(1),
            }, {"files": {"q01.json": "f" * 64, "q09.json": "0" * 64}})
            report = scan_candidate_dir(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any(
                "digest mismatch for q01.json" in finding
                for finding in report["findings"]
            ))
            self.assertTrue(any(
                "unknown file q09.json" in finding for finding in report["findings"]
            ))

    def test_unexpected_file_is_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = stage(temporary, {"q01.json": make_question(1)})
            (root / "notes.txt").write_text("draft", encoding="utf-8")
            report = scan_candidate_dir(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any(
                "unexpected file" in finding for finding in report["findings"]
            ))

    def test_missing_directory(self) -> None:
        report = scan_candidate_dir(r"Z:\definitely\not\here")
        self.assertFalse(report["ok"])
        self.assertEqual(0, report["question_count"])


if __name__ == "__main__":
    unittest.main()
