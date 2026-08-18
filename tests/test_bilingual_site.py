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
