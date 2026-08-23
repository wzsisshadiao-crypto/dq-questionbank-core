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
SCROLL_SCRIPT = REPOSITORY_ROOT / "tests" / "js" / "test_editor_scroll_sync.js"


class EditorScrollSyncTests(unittest.TestCase):
    def test_focused_scroll_sync_runs_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the focused scroll-sync tests")
        completed = subprocess.run(
            [node, str(SCROLL_SCRIPT)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            f"scroll-sync checks failed:\n{completed.stdout}\n{completed.stderr}",
        )
        self.assertIn("scroll-sync checks passed", completed.stdout)

    def test_served_workspace_exposes_the_scroll_sync_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = create_server(Path(temporary), port=0)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", "/app.js")
                response = connection.getresponse()
                script = response.read().decode("utf-8")
                connection.close()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()

        self.assertIn("function activeEditorFieldFromScroll()", script)
        self.assertIn('window.addEventListener(\n  "scroll"', script)
        self.assertIn("{ passive: true }", script)
        self.assertIn("requestAnimationFrame(activeEditorFieldFromScroll)", script)
        self.assertIn("state.activeEditorField = field", script)
        self.assertIn("editorNavScrollLockUntil = Date.now() + 700", script)
        self.assertIn("section.getBoundingClientRect().top <= reference", script)


if __name__ == "__main__":
    unittest.main()
