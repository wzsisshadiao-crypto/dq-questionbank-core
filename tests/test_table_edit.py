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
TABLE_EDIT_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_table_edit.js"


class TableEditingContractTests(unittest.TestCase):
    def test_focused_table_edit_workflow_runs_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused table-edit tests")
        completed = subprocess.run(
            [node, str(TABLE_EDIT_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"table-edit checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("table-edit checks passed", completed.stdout)

    def test_served_workspace_exposes_structural_table_editing(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = create_server(Path(temporary), port=0)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_port
                )
                connection.request("GET", "/table_edit.js")
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

        self.assertIn("function splitEditableContent", script)
        self.assertIn("function mergeEditableContent", script)
        self.assertIn("[[table-", script)
        self.assertIn("table_edit.js", page)
        self.assertIn("function renderTableGrids(", app)
        self.assertIn("function collectTableBlocks(", app)
        self.assertIn("mergeEditableField(", app)
        self.assertIn("table-cell-input", app)
        self.assertIn("originalStemTables", app)


if __name__ == "__main__":
    unittest.main()
