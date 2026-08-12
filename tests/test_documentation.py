from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_docs import find_broken_links  # noqa: E402


class DocumentationTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        self.assertEqual(find_broken_links(), [])
