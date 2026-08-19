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
    def test_both_public_web_roots_are_english_only(self):
        root = Path(__file__).resolve().parents[1] / "src"
        web_roots = (
            root / "dq_questionbank" / "web",
            root / "dq_questionbank_local" / "web",
        )
        for web_root in web_roots:
            for target in web_root.rglob("*"):
                if not target.is_file() or target.suffix not in {".css", ".html", ".js"}:
                    continue
                with self.subTest(target=target):
                    text = target.read_text(encoding="utf-8")
                    self.assertIsNone(
                        re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text)
                    )

    def test_normative_public_interface_contains_no_unreviewed_cjk_text(self):
        root = Path(__file__).resolve().parents[1]
        public_extensions = {".css", ".html", ".js", ".json", ".md", ".py", ".toml", ".yml"}
        ignored_parts = {
            "build",
            "dist",
            "_site",
            "workspace",
            ".git",
            "__pycache__",
            ".egg-info",
        }
        multilingual_data_parts = {"examples", "fixtures"}
        localized_files = {Path("README.zh-CN.md")}
        localized_directories = {Path("site/zh-CN")}
        targets = (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix in public_extensions
            and not any(part in ignored_parts for part in path.parts)
            and not any(part in multilingual_data_parts for part in path.parts)
            and path.relative_to(root) not in localized_files
            and not any(
                path.relative_to(root).is_relative_to(directory)
                for directory in localized_directories
            )
        )
        for target in targets:
            text = target.read_text(encoding="utf-8")
            text = text.replace("简体中文", "")
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

    def test_local_workspace_exposes_mature_english_navigation_and_filters(self):
        root = Path(__file__).resolve().parents[1]
        document = root / "src" / "dq_questionbank_local" / "web" / "index.html"
        text = document.read_text(encoding="utf-8")
        self.assertIn('<body class="dark-theme">', text)
        for label in (
            "Question Bank",
            "Paper Center",
            "Import Center",
            "Editor Center",
            "Bank Data",
            "Quality Center",
            "Review Center",
            "Image Repair",
            "Export Center",
            "Recycle Bin",
        ):
            self.assertIn(label, text)
        for control_id in (
            "paper-nav",
            "import-nav",
            "data-nav",
            "quality-nav",
            "review-nav",
            "export-nav",
            "question-year",
            "question-search",
            "question-search-scope",
            "collection-search",
            "editor-question-select",
            "editor-field-nav",
        ):
            self.assertIn(f'id="{control_id}"', text)
        self.assertNotRegex(
            text,
            r'<button[^>]+id="import-nav"[^>]+disabled',
        )
        for view_id in (
            "paper-view",
            "import-view",
            "data-view",
            "quality-view",
            "review-view",
            "export-view",
        ):
            self.assertIn(f'id="{view_id}"', text)
        for editor_control in (
            "editor-context-id",
            "editor-context-source",
            "editor-save-state",
            "editor-run-quality",
            "editor-open-quality",
        ):
            self.assertIn(f'id="{editor_control}"', text)

    def test_editor_field_navigation_exposes_one_active_state(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "src" / "dq_questionbank_local" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "src" / "dq_questionbank_local" / "web" / "app.js").read_text(encoding="utf-8")
        styles = (root / "src" / "dq_questionbank_local" / "web" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('data-editor-field="stem" aria-current="true"', html)
        self.assertIn("function setActiveEditorField(field)", script)
        self.assertIn('button.classList.toggle("active", active)', script)
        self.assertIn('button.setAttribute("aria-current", "true")', script)
        self.assertIn('setActiveEditorField(button.dataset.editorField)', script)
        self.assertIn(".editor-field-nav button.active", styles)
        self.assertIn(".editor-field-nav button:focus-visible", styles)
