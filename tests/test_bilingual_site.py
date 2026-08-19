from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_site import build_site

ROOT = Path(__file__).resolve().parents[1]


class BilingualSiteTests(unittest.TestCase):
    def test_bilingual_pages_link_to_each_other_and_use_real_workspace_images(self):
        english = (ROOT / "site" / "en" / "index.html").read_text(encoding="utf-8")
        chinese = (ROOT / "site" / "zh-CN" / "index.html").read_text(encoding="utf-8")
        self.assertIn('../zh-CN/', english)
        self.assertIn('../en/', chinese)
        self.assertIn("question-bank-workspace.png", english)
        self.assertIn("question-bank-workspace-zh.png", chinese)
        self.assertIn("DX_SX_154", chinese)
        self.assertIn("\u4e2d\u6587\u9898\u5e93", chinese)
        self.assertIn("LaTeX \u516c\u5f0f", chinese)

    def test_root_site_defaults_to_english_and_keeps_explicit_language_links(self):
        root = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('window.location.replace("./en/")', root)
        self.assertNotIn("navigator.language", root)
        self.assertIn('href="./zh-CN/"', root)

    def test_site_build_copies_both_reviewed_screenshots(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "site-output"
            build_site(output)
            self.assertTrue((output / "en" / "index.html").is_file())
            self.assertTrue((output / "zh-CN" / "index.html").is_file())
            self.assertGreater((output / "assets" / "question-bank-workspace.png").stat().st_size, 1000)
            self.assertGreater(
                (output / "assets" / "question-bank-workspace-zh.png").stat().st_size,
                1000,
            )


if __name__ == "__main__":
    unittest.main()
