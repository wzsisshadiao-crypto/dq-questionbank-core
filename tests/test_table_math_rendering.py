from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from dq_questionbank import validate_with_schema

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RENDERING_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_table_math_rendering.js"
FIXTURE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "rendering" / "table-math-question.json"
)


class TableMathRenderingTests(unittest.TestCase):
    def test_focused_rendering_workflow_runs_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused rendering tests")
        completed = subprocess.run(
            [node, str(RENDERING_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"rendering checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("rendering checks passed", completed.stdout)

    def test_fixture_is_valid_synthetic_data_with_table_and_math(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

        self.assertEqual([], validate_with_schema(payload))
        block_types = {
            block["type"]
            for question in payload["questions"]
            for block in question["stem"]["blocks"]
        }
        self.assertIn("table", block_types)
        self.assertIn("math", block_types)
        for question in payload["questions"]:
            types = [block["type"] for block in question["stem"]["blocks"]]
            self.assertIn("table", types)
            self.assertIn("math", types)

    def test_blank_cell_fixture_keeps_table_shape_through_the_canonical_model(self):
        from dq_questionbank import QuestionSet

        payload = json.loads(
            (
                REPOSITORY_ROOT
                / "tests"
                / "fixtures"
                / "rendering"
                / "blank-cell-table.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual([], validate_with_schema(payload))
        table = next(
            block
            for block in payload["questions"][0]["stem"]["blocks"]
            if block["type"] == "table"
        )
        self.assertEqual(["Step", "Checkpoint"], table["rows"][0])
        self.assertEqual("", table["rows"][2][1], "the blank cell stays an empty string")

        restored = QuestionSet.from_dict(payload)
        self.assertEqual(payload, restored.to_dict())


if __name__ == "__main__":
    unittest.main()
