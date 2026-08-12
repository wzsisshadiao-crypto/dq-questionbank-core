from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


class InterfaceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.html_language = None
        self.ids = []
        self.controls = []
        self.labels = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "html":
            self.html_language = attributes.get("lang")
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag in {"button", "textarea", "input"} and attributes.get("type") != "hidden":
            self.controls.append((tag, attributes))
        if tag == "label" and "for" in attributes:
            self.labels.append(attributes["for"])


class EnglishInterfaceTests(unittest.TestCase):
    def test_public_interface_contains_no_cjk_text(self):
        root = Path(__file__).resolve().parents[1]
        public_extensions = {".css", ".html", ".js", ".json", ".md", ".py", ".toml", ".yml"}
        ignored_parts = {"build", "dist", ".git", "__pycache__", ".egg-info"}
        targets = (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix in public_extensions
            and not any(part in ignored_parts for part in path.parts)
        )
        for target in targets:
            text = target.read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text), target
            )
            self.assertNotIn("\ufffd", text, f"Replacement character found in {target}")

    def test_playground_has_basic_accessibility_metadata(self):
        root = Path(__file__).resolve().parents[1]
        document = root / "src" / "dq_questionbank" / "web" / "index.html"
        parser = InterfaceParser()
        parser.feed(document.read_text(encoding="utf-8"))

        self.assertEqual(parser.html_language, "en")
        self.assertEqual(len(parser.ids), len(set(parser.ids)), "HTML ids must be unique")
        labelled_control_ids = set(parser.labels)
        for tag, attributes in parser.controls:
            has_name = bool(attributes.get("aria-label") or attributes.get("title"))
            has_label = attributes.get("id") in labelled_control_ids
            if tag != "button":
                self.assertTrue(has_name or has_label, f"Unlabelled {tag}: {attributes}")
