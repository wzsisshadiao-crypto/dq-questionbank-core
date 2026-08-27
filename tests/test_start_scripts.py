from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StartScriptsTests(unittest.TestCase):
    """Pin the double-click launcher contract for fresh checkouts."""

    def test_windows_launcher_runs_run_py_from_the_checkout(self) -> None:
        batch = (ROOT / "start.bat").read_text(encoding="utf-8")
        self.assertIn("run.py", batch)
        self.assertIn("%~dp0", batch)  # always runs from the checkout root
        for fallback in ("py -3", "python"):
            self.assertIn(fallback, batch)
        self.assertIn("pause", batch)  # double-clickers see errors, not a flash

    def test_posix_launcher_runs_run_py_from_the_checkout(self) -> None:
        shell = (ROOT / "start.sh").read_text(encoding="utf-8")
        self.assertIn("run.py", shell)
        self.assertIn("python3", shell)
        self.assertIn('dirname "$0"', shell)

    def test_run_py_opens_the_browser_without_extra_flags(self) -> None:
        source = (ROOT / "run.py").read_text(encoding="utf-8")
        self.assertIn("--open-browser", source)

    def test_launchers_are_secret_scanned_by_the_audit(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from audit_public_tree import TEXT_SUFFIXES
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        self.assertIn(".bat", TEXT_SUFFIXES)
        self.assertIn(".sh", TEXT_SUFFIXES)


if __name__ == "__main__":
    unittest.main()
