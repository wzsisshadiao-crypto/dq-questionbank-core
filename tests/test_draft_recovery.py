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
DRAFT_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_draft_recovery.js"


class DraftRecoveryContractTests(unittest.TestCase):
    def test_focused_draft_recovery_checks_run_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused draft-recovery tests")
        completed = subprocess.run(
            [node, str(DRAFT_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"draft recovery checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("draft recovery checks passed", completed.stdout)

    def test_served_workspace_exposes_draft_recovery_script(self):
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
                connection.request("GET", "/draft_recovery.js")
                script_response = connection.getresponse()
                script = script_response.read().decode("utf-8")
                connection.close()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()

        self.assertEqual(200, response.status)
        self.assertEqual(200, script_response.status)
        self.assertIn('src="/draft_recovery.js"', page)
        self.assertIn("dq-questionbank:draft:v1:", script)
        self.assertIn("localStorage.setItem", script)
        self.assertIn("Restore draft", script)
        self.assertIn("Discard draft", script)
        self.assertIn('window.addEventListener("beforeunload"', script)
        self.assertIn("!removeQuestionButton.isConnected", script)


if __name__ == "__main__":
    unittest.main()
