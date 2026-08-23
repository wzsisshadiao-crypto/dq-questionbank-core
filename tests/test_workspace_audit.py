from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dq_questionbank.cli import main as cli_main
from dq_questionbank.models import Asset, Content, ContentBlock, Question, QuestionSet
from dq_questionbank.sqlite_storage import SqliteStorageAdapter
from dq_questionbank.storage import FilesystemStorageAdapter
from dq_questionbank.workspace_audit import (
    CODE_BROKEN_REFERENCE,
    CODE_INDEX_DRIFT,
    CODE_ORPHAN_ASSET,
    CODE_UNREADABLE,
    WORKSPACE_AUDIT_VERSION,
    WorkspaceAuditReport,
    audit_workspace,
)


def _question(question_id: str, *, asset_uri: str | None = None) -> Question:
    assets = (
        [Asset(id=f"{question_id}-img", kind="image", uri=asset_uri)]
        if asset_uri
        else []
    )
    return Question(
        id=question_id,
        type="short_answer",
        stem=Content([ContentBlock(type="text", text=f"Stem {question_id}.")]),
        assets=assets,
    )


def _set_file(root: Path, set_id: str, questions: list[Question]) -> None:
    FilesystemStorageAdapter(root).save(
        QuestionSet(id=set_id, title=f"Set {set_id}", questions=questions)
    )


class WorkspaceAuditTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def test_healthy_workspace_reports_no_issues(self):
        (self.assets / "fig-1.png").write_bytes(b"png")
        _set_file(self.root, "set-a", [_question("q1", asset_uri="fig-1.png")])
        report = audit_workspace(self.root)
        self.assertTrue(report.ok)
        self.assertEqual(report.sets_checked, 1)
        self.assertEqual(report.references_checked, 1)
        self.assertEqual(report.assets_checked, 1)
        self.assertEqual(report.rows_checked, 0)

    def test_broken_reference_and_orphan_are_reported(self):
        (self.assets / "orphan.png").write_bytes(b"png")
        _set_file(self.root, "set-a", [_question("q1", asset_uri="missing.png")])
        report = audit_workspace(self.root)
        codes = [issue.code for issue in report.issues]
        self.assertIn(CODE_BROKEN_REFERENCE, codes)
        self.assertIn(CODE_ORPHAN_ASSET, codes)
        locations = [issue.location for issue in report.issues]
        self.assertIn("set-a/q1/q1-img", locations)
        self.assertIn("orphan.png", locations)

    def test_subquestion_assets_are_walked(self):
        (self.assets / "sub.png").write_bytes(b"png")
        parent = _question("q1")
        parent.subquestions.append(_question("q1a", asset_uri="sub.png"))
        _set_file(self.root, "set-a", [parent])
        report = audit_workspace(self.root)
        self.assertTrue(report.ok)
        self.assertEqual(report.references_checked, 1)

    def test_unreadable_set_is_reported(self):
        sets_dir = self.root / "question_sets"
        sets_dir.mkdir(exist_ok=True)
        (sets_dir / "broken.json").write_text("{ not json", encoding="utf-8")
        report = audit_workspace(self.root)
        self.assertFalse(report.ok)
        self.assertEqual(report.issues[0].code, CODE_UNREADABLE)



    def test_index_drift_is_detected_read_only(self):
        database = self.root / "bank.db"
        question_set = QuestionSet(id="set-a", title="Set A", questions=[_question("q1")])
        SqliteStorageAdapter(database).save(question_set)
        drift = sqlite3.connect(database)
        drift.execute("UPDATE question_sets SET question_count = 9 WHERE id = 'set-a'")
        drift.commit()
        drift.close()
        report = audit_workspace(self.root, database=database)
        codes = [issue.code for issue in report.issues]
        self.assertIn(CODE_INDEX_DRIFT, codes)
        self.assertEqual(report.rows_checked, 1)
        details = [issue.detail for issue in report.issues]
        self.assertTrue(any("question_count 9 != 1" in item for item in details))

    def test_https_and_data_uris_are_never_file_references(self):
        _set_file(
            self.root,
            "set-a",
            [
                _question("q1", asset_uri="https://example.com/x.png"),
                _question("q2", asset_uri="data:image/png;base64,AAAA"),
            ],
        )
        report = audit_workspace(self.root)
        self.assertEqual(report.references_checked, 0)
        self.assertTrue(report.ok)

    def test_report_round_trip_and_unknown_key_rejection(self):
        (self.assets / "fig.png").write_bytes(b"png")
        _set_file(self.root, "set-a", [_question("q1", asset_uri="gone.png")])
        payload = audit_workspace(self.root).to_dict()
        restored = WorkspaceAuditReport.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        payload["note"] = "extra"
        with self.assertRaises(ValueError):
            WorkspaceAuditReport.from_dict(payload)

    def test_version_is_stable(self):
        self.assertEqual(WORKSPACE_AUDIT_VERSION, "workspace-audit/1")


class AuditCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "assets").mkdir()
        self.addCleanup(self._tmp.cleanup)

    def test_cli_exits_zero_for_healthy_workspace(self):
        (self.root / "assets" / "fig.png").write_bytes(b"png")
        _set_file(self.root, "set-a", [_question("q1", asset_uri="fig.png")])
        self.assertEqual(cli_main(["audit", str(self.root)]), 0)

    def test_cli_exits_one_and_prints_issues_for_drift(self):
        _set_file(self.root, "set-a", [_question("q1", asset_uri="missing.png")])
        self.assertEqual(cli_main(["audit", str(self.root)]), 1)

    def test_cli_json_output_round_trips(self):
        import contextlib
        import io

        _set_file(self.root, "set-a", [_question("q1")])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli_main(["audit", str(self.root), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["version"], "workspace-audit/1")
        self.assertTrue(WorkspaceAuditReport.from_dict(payload).ok)

    def test_cli_reports_missing_database_as_error(self):
        import contextlib
        import io

        _set_file(self.root, "set-a", [_question("q1")])
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = cli_main(
                ["audit", str(self.root), "--database", str(self.root / "nope.db")]
            )
        self.assertEqual(code, 2)
        self.assertIn("Audit error", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
