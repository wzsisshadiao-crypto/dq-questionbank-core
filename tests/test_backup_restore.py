from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DRILL_SCRIPT = REPOSITORY_ROOT / "examples" / "backup_restore_drill.py"


def make_workspace(root: Path) -> Path:
    workspace = root / "workspace"
    (workspace / "question_sets").mkdir(parents=True)
    (workspace / "workspace.json").write_text("{}\n", encoding="utf-8")
    payload = {
        "schema_version": "1.0",
        "id": "drill-demo",
        "title": "Drill demo",
        "questions": [],
    }
    (workspace / "question_sets" / "drill-demo.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return workspace


class BackupRestoreDrillTests(unittest.TestCase):
    def run_drill(self, workspace: Path):
        return subprocess.run(
            [sys.executable, str(DRILL_SCRIPT), "--workspace", str(workspace)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_drill_round_trips_a_synthetic_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary))
            before = {
                item.relative_to(workspace).as_posix(): item.read_bytes()
                for item in workspace.rglob("*")
                if item.is_file()
            }

            completed = self.run_drill(workspace)

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("backup verified and restored", completed.stdout)
            self.assertIn("byte-identical", completed.stdout)
            after = {
                item.relative_to(workspace).as_posix(): item.read_bytes()
                for item in workspace.rglob("*")
                if item.is_file()
            }
            self.assertEqual(before, after)
            backup_dir = Path(temporary) / "workspace.backup-drill"
            manifest = json.loads(
                (backup_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(2, len(manifest["workspace_files"]))

    def test_drill_refuses_to_merge_into_an_existing_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary))

            first = self.run_drill(workspace)
            second = self.run_drill(workspace)

            self.assertEqual(0, first.returncode)
            self.assertEqual(1, second.returncode)
            self.assertIn("already exists", second.stderr)

    def test_tampered_backup_fails_verification_before_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary))
            backup_dir = Path(temporary) / "custom-backup"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(DRILL_SCRIPT),
                    "--workspace",
                    str(workspace),
                    "--backup-dir",
                    str(backup_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode)

            target = backup_dir / "workspace.json"
            target.write_text("tampered\n", encoding="utf-8")
            (workspace / "workspace.json").write_text("later edit\n", encoding="utf-8")

            failed = subprocess.run(
                [
                    sys.executable,
                    str(DRILL_SCRIPT),
                    "--workspace",
                    str(workspace),
                    "--backup-dir",
                    str(backup_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(1, failed.returncode)
            self.assertIn("drill failed", failed.stderr)
            self.assertEqual(
                "later edit\n",
                (workspace / "workspace.json").read_text(encoding="utf-8"),
                "a tampered backup never overwrites the workspace",
            )


if __name__ == "__main__":
    unittest.main()
