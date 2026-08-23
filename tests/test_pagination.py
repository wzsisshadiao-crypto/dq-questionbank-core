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
PAGINATION_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_pagination.js"


class PaginationContractTests(unittest.TestCase):
    def test_focused_pagination_workflow_runs_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused pagination tests")
        completed = subprocess.run(
            [node, str(PAGINATION_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"pagination checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("pagination checks passed", completed.stdout)

    def test_served_workspace_exposes_the_pagination_control(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = create_server(Path(temporary), port=0)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_port
                )
                connection.request("GET", "/pagination.js")
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

        self.assertIn("function createPagination", script)
        self.assertIn("function renderPaginationControls", script)
        self.assertIn("ArrowLeft", script)
        self.assertIn('id="question-pagination"', page)
        self.assertIn("questionPagination.sliceFor(matches)", app)
        self.assertIn("function applyQuestionFilters()", app)
        self.assertIn("typeof fetchWithRetries === \"function\"", app)


if __name__ == "__main__":
    unittest.main()
