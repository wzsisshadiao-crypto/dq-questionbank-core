from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank.formats.docx import DocxImporter

FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "community"
    / "docx-choice-answer-label"
)


@unittest.skipIf(importlib.util.find_spec("docx") is None, "python-docx is optional")
class DocxFixtureTests(unittest.TestCase):
    def test_json_style_choice_answer_imports_without_quote_characters(self):
        import docx

        fixture = json.loads((FIXTURE_DIR / "fixture.json").read_text(encoding="utf-8"))
        document = docx.Document()
        document.core_properties.title = fixture["title"]
        for paragraph in fixture["paragraphs"]:
            document.add_paragraph(paragraph["text"], style=paragraph.get("style"))

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "choice-answer.docx"
            document.save(source)
            imported = DocxImporter().load(source)

        expected = fixture["expected"]
        self.assertEqual(len(imported.questions), 1)
        question = imported.questions[0]
        self.assertEqual(question.id, expected["question_id"])
        self.assertEqual(question.type, expected["type"])
        self.assertEqual(question.language, expected["language"])
        self.assertEqual([choice.id for choice in question.choices], expected["choice_ids"])
        self.assertEqual(question.answer.to_dict(), expected["answer"])


if __name__ == "__main__":
    unittest.main()
