from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from dq_questionbank.formats.docx import DocxExporter, DocxImporter
from dq_questionbank.formats.json_format import JsonExporter, JsonImporter
from dq_questionbank.formats.latex import LatexExporter, LatexImporter
from dq_questionbank.formats.markdown import MarkdownExporter, MarkdownImporter
from dq_questionbank.models import Asset, Content, ContentBlock, Question, QuestionSet

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample_questions.json"


class FormatTests(unittest.TestCase):
    def setUp(self):
        from dq_questionbank.models import QuestionSet

        self.sample_set = QuestionSet.from_dict(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))
        self.temporary = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_json_round_trip(self):
        target = self.tmp_path / "questions.json"
        JsonExporter().dump(self.sample_set, target)
        self.assertEqual(JsonImporter().load(target).to_dict(), self.sample_set.to_dict())

    def test_markdown_round_trip_preserves_canonical_data(self):
        target = self.tmp_path / "questions.md"
        MarkdownExporter().dump(self.sample_set, target)
        imported = MarkdownImporter().load(target)
        self.assertEqual(imported.to_dict(), self.sample_set.to_dict())

    def test_latex_round_trip_preserves_canonical_data(self):
        target = self.tmp_path / "questions.tex"
        LatexExporter().dump(self.sample_set, target)
        imported = LatexImporter().load(target)
        self.assertEqual(imported.to_dict(), self.sample_set.to_dict())
        self.assertIn("\\documentclass", target.read_text(encoding="utf-8"))

    def test_simple_latex_enumerate_import(self):
        source = self.tmp_path / "simple.tex"
        source.write_text(
            r"\begin{enumerate}\item First question?\item Second question?\end{enumerate}",
            encoding="utf-8",
        )
        imported = LatexImporter().load(source)
        self.assertEqual(len(imported.questions), 2)

    @unittest.skipIf(importlib.util.find_spec("docx") is None, "python-docx is optional")
    def test_docx_generated_document_round_trip_core_fields(self):
        target = self.tmp_path / "questions.docx"
        DocxExporter().dump(self.sample_set, target)
        imported = DocxImporter().load(target)
        self.assertEqual(
            [question.id for question in imported.questions], ["math-001", "science-001"]
        )
        self.assertEqual(imported.questions[0].type, "single_choice")
        self.assertTrue(imported.questions[0].stem.plain_text().startswith("If"))
        self.assertEqual(
            [choice.id for choice in imported.questions[0].choices], ["A", "B", "C", "D"]
        )
        self.assertEqual(
            [question.id for question in imported.questions[1].subquestions],
            ["science-001-a", "science-001-b"],
        )

    @unittest.skipIf(importlib.util.find_spec("docx") is None, "python-docx is optional")
    def test_docx_extracts_embedded_image_to_explicit_asset_directory(self):
        image_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        image_path = self.tmp_path / "pixel.png"
        image_path.write_bytes(image_bytes)
        question_set = QuestionSet(
            "image-set",
            "Image Set",
            [
                Question(
                    "image-001",
                    "short_answer",
                    Content(
                        [ContentBlock(type="image", asset_id="diagram", alt_text="Synthetic pixel")]
                    ),
                    assets=[Asset("diagram", "image", "pixel.png", "image/png")],
                )
            ],
        )
        target = self.tmp_path / "image.docx"
        DocxExporter().dump(question_set, target, assets_base=self.tmp_path)
        extracted = self.tmp_path / "extracted"
        imported = DocxImporter().load(target, assets_dir=extracted)
        self.assertEqual(len(imported.questions[0].assets), 1)
        self.assertTrue(next(extracted.iterdir()).is_file())
