from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from dq_questionbank import (
    ImportBundleError,
    export_reviewed_questions,
    list_import_cases,
    prepare_import_bundle,
    prepare_import_case,
    review_import_session,
    run_import_case,
)
from dq_questionbank.cli import main

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "src" / "dq_questionbank" / "data" / "import_cases"
CASE_IDS = (
    "manual-web",
    "web-ai",
    "coding-word",
    "coding-pdf",
    "coding-exam-omml",
    "pdf-table",
)


class ImportCaseTests(unittest.TestCase):
    def test_six_routes_are_discoverable(self):
        cases = list_import_cases()
        self.assertEqual(tuple(case.id for case in cases), CASE_IDS)
        self.assertEqual(
            {case.route for case in cases},
            {"manual_web", "web_ai", "ai_coding", "ai_coding_pdf", "ai_coding_exam_omml"},
        )

    def test_every_case_runs_through_review_and_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            for case_id in CASE_IDS:
                paths = run_import_case(case_id, Path(temporary) / case_id)
                candidate = json.loads(Path(paths["candidate_session"]).read_text(encoding="utf-8"))
                reviewed = json.loads(Path(paths["reviewed_session"]).read_text(encoding="utf-8"))
                exported = json.loads(Path(paths["question_set"]).read_text(encoding="utf-8"))
                self.assertEqual(candidate["status"], "candidate_ready")
                self.assertEqual(reviewed["status"], "reviewed")
                self.assertTrue(exported["questions"])
            exam_path = (
                Path(temporary)
                / "coding-exam-omml"
                / "coding-exam-omml.reviewed-session.json"
            )
            exam = json.loads(exam_path.read_text(encoding="utf-8"))
            self.assertEqual(
                {item["question_id"]: item["decision"] for item in exam["candidates"]},
                {"exam-001": "accepted", "exam-002": "rejected"},
            )

    def test_candidate_session_must_be_reviewed_before_export(self):
        with self.assertRaisesRegex(ImportBundleError, "explicit review decision"):
            export_reviewed_questions(prepare_import_case("manual-web"))

    def test_tampered_session_digest_is_rejected(self):
        session = prepare_import_case("manual-web")
        session["candidates"][0]["question"]["stem"]["blocks"][0]["text"] = "tampered"
        with self.assertRaisesRegex(ImportBundleError, "digest is stale"):
            export_reviewed_questions(session)

    def test_review_decision_is_one_way(self):
        session = prepare_import_case("manual-web")
        candidate = session["candidates"][0]
        decisions = {
            "decisions": [
                {
                    "question_id": candidate["question_id"],
                    "candidate_sha256": candidate["question_sha256"],
                    "decision": "accepted",
                }
            ]
        }
        reviewed = review_import_session(session, decisions)
        decisions["decisions"][0]["decision"] = "rejected"
        with self.assertRaisesRegex(ImportBundleError, "already reviewed"):
            review_import_session(reviewed, decisions)

    def test_bundle_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "bundle"
            shutil.copytree(CASES / "manual-web", target)
            manifest_path = target / "bundle.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source"]["path"] = "../form-submission.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ImportBundleError, "Unsafe bundle path"):
                prepare_import_bundle(target)

    def test_ai_proposal_cannot_cross_field_allowlist(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "bundle"
            shutil.copytree(CASES / "web-ai", target)
            proposal_path = target / "proposal.json"
            proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
            proposal["changes"][0]["field"] = "id"
            proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
            manifest_path = target / "bundle.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["proposal"]["sha256"] = hashlib.sha256(proposal_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ImportBundleError, "allowed field boundary"):
                prepare_import_bundle(target)

    def test_pdf_and_exam_sources_are_real_declared_formats(self):
        self.assertEqual((CASES / "coding-pdf" / "worksheet.pdf").read_bytes()[:5], b"%PDF-")
        with zipfile.ZipFile(CASES / "coding-exam-omml" / "synthetic-exam.docx") as document:
            xml = document.read("word/document.xml")
        self.assertIn(b"<m:oMath", xml)

    def test_case_output_directory_cannot_be_a_symbolic_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            linked = root / "linked"
            try:
                linked.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("Symbolic links are unavailable in this environment.")
            with self.assertRaisesRegex(ImportBundleError, "symbolic link"):
                run_import_case("manual-web", linked)

    def test_cli_lists_and_runs_cases(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main(["intake", "cases"]), 0)
        self.assertIn("coding-exam-omml", stdout.getvalue())
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()), redirect_stderr(
            StringIO()
        ):
            self.assertEqual(main(["intake", "run", "coding-pdf", "-o", temporary]), 0)
            self.assertTrue((Path(temporary) / "coding-pdf.question-set.json").is_file())


if __name__ == "__main__":
    unittest.main()
