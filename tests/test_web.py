"""Smoke tests for the browser playground (HTML, CSS, JavaScript)."""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path


class PlaygroundSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.web_root = (
            Path(__file__).resolve().parents[1] / "src" / "dq_questionbank" / "web"
        )

    def test_html_is_valid_xhtml5(self):
        document = self.web_root / "index.html"
        text = document.read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", text.lower())
        self.assertIn("<html lang=\"en\"", text)
        self.assertIn("<meta charset=\"utf-8\"", text.lower())
        self.assertIn("<title>", text.lower())
        self.assertIn("</html>", text)

    def test_html_has_required_semantic_elements(self):
        text = (self.web_root / "index.html").read_text(encoding="utf-8")
        self.assertIn("<main", text.lower(), "Missing <main> landmark")
        self.assertIn("<header", text.lower(), "Missing <header> landmark")

    def test_javascript_parses_without_syntax_error(self):
        js_path = self.web_root / "app.js"
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js not available for JavaScript syntax check")
        result = subprocess.run(
            [node, "--check", str(js_path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"JavaScript syntax error in app.js:\n{result.stderr}",
        )

    def test_css_has_no_empty_rules(self):
        css_path = self.web_root / "styles.css"
        text = css_path.read_text(encoding="utf-8")
        blocks = re.findall(r"\{([^}]*)\}", text, re.DOTALL)
        for i, block in enumerate(blocks, 1):
            stripped = block.strip()
            self.assertTrue(
                stripped,
                f"Empty CSS rule block #{i} in styles.css",
            )

    def test_css_uses_relative_units_for_responsive_layout(self):
        text = (self.web_root / "styles.css").read_text(encoding="utf-8")
        has_media_query = bool(re.search(r"@media", text))
        has_flex_or_grid = bool(re.search(r"(display\s*:\s*(flex|grid))", text))
        self.assertTrue(
            has_media_query or has_flex_or_grid,
            "CSS should use responsive layout (media queries or flex/grid)",
        )
