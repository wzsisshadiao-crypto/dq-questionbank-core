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
RECYCLE_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_recycle_bin.js"


class RecycleBinContractTests(unittest.TestCase):
    def test_focused_recycle_workflow_runs_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused recycle-bin tests")
        completed = subprocess.run(
            [node, str(RECYCLE_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"recycle checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("recycle checks passed", completed.stdout)

    def test_served_workspace_exposes_the_recycle_bin_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = create_server(Path(temporary), port=0)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_port
                )
                connection.request("GET", "/")
                response = connection.getresponse()
                page = response.read().decode("utf-8")
                connection.request("GET", "/app.js")
                script = connection.getresponse().read().decode("utf-8")
                connection.close()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()

        self.assertIn('id="recycle-nav"', page)
        self.assertIn('id="recycle-view"', page)
        self.assertIn('id="recycle-list"', page)
        self.assertIn("Recycle Bin", page)
        self.assertIn("function recycleQuestion(questionId)", script)
        self.assertIn("function restoreQuestion(questionId)", script)
        self.assertIn("function permanentlyDeleteQuestion(questionId)", script)
        self.assertIn("!state.recycleIds.includes(question.id)", script)
        self.assertIn("Delete permanently", script)
        self.assertIn("Recycle", script)


if __name__ == "__main__":
    unittest.main()
