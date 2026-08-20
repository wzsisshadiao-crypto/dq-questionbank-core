from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FORMULA_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_formula_blocks.js"


class FormulaBlockWorkflowTests(unittest.TestCase):
    def test_focused_formula_workflow_runs_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused formula-block tests")
        completed = subprocess.run(
            [node, str(FORMULA_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"formula checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("formula checks passed", completed.stdout)

    def test_editor_markup_exposes_formula_workflow_controls(self):
        root = Path(__file__).resolve().parents[1] / "src" / "dq_questionbank_local" / "web"
        markup = (root / "index.html").read_text(encoding="utf-8")
        script = (root / "app.js").read_text(encoding="utf-8")
        for control_id in (
            "formula-dialog",
            "formula-form",
            "formula-mode",
            "formula-source",
            "formula-preview",
            "formula-error",
            "formula-cancel",
            "formula-apply",
        ):
            self.assertIn(f'id="{control_id}"', markup)
        self.assertIn('src="/formula.js"', markup)
        self.assertIn("Insert formula", markup)
        self.assertIn("function openFormulaEditor(textarea, range = null)", script)
        self.assertIn("function applyFormulaEdit()", script)
        self.assertIn("function updateFormulaPreview()", script)
        self.assertIn("dqFormula.findFormulaRange", script)
        self.assertIn("renderTextWithMath(container, value, true)", script)
        self.assertIn('math.classList.add("formula-block")', script)


if __name__ == "__main__":
    unittest.main()
