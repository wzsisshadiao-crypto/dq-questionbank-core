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
RETRY_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_fetch_with_retries.js"


class FetchWithRetriesContractTests(unittest.TestCase):
    def test_focused_retry_workflow_runs_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused fetch-retry tests")
        completed = subprocess.run(
            [node, str(RETRY_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"fetch-retry checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("fetch-with-retries checks passed", completed.stdout)

    def test_served_workspace_exposes_the_retry_helper(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = create_server(Path(temporary), port=0)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_port
                )
                connection.request("GET", "/fetch_with_retries.js")
                script = connection.getresponse().read().decode("utf-8")
                connection.request("GET", "/")
                page = connection.getresponse().read().decode("utf-8")
                connection.close()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()

        self.assertIn("function fetchWithRetries", script)
        self.assertIn("class FetchRetryError", script)
        self.assertIn("AbortController", script)
        self.assertIn("computeBackoffDelay", script)
        self.assertIn("fetch_with_retries.js", page)
        self.assertIn("pagination.js", page)


if __name__ == "__main__":
    unittest.main()
