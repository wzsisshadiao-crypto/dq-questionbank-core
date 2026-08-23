from __future__ import annotations

import http.client
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from dq_questionbank_local.server import create_server

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RICH_EDIT_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_rich_edit.js"


class RichFormulaEditingContractTests(unittest.TestCase):
    def test_focused_rich_edit_workflow_runs_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused rich-edit tests")
        completed = subprocess.run(
            [node, str(RICH_EDIT_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"rich-edit checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("rich-edit checks passed", completed.stdout)

    def test_served_workspace_exposes_the_rich_formula_editor(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = create_server(Path(temporary), port=0)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_port
                )
                connection.request("GET", "/rich_edit.js")
                script = connection.getresponse().read().decode("utf-8")
                connection.request("GET", "/app.js")
                app = connection.getresponse().read().decode("utf-8")
                connection.request("GET", "/")
                page = connection.getresponse().read().decode("utf-8")
                connection.close()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()

        self.assertIn("function createRichFormulaEditor", script)
        self.assertIn("function moveMathBlock", script)
        self.assertIn("function projectForEditing", script)
        self.assertIn("function repairCaret", script)
        self.assertIn('id="formula-rich-host"', page)
        self.assertIn("rich_edit.js", page)
        self.assertIn("createRichFormulaEditor(formulaRichHost", app)
        self.assertIn("formulaRichEditor.refresh()", app)
        self.assertIn("formulaRichHost.focus()", app)


if __name__ == "__main__":
    unittest.main()
