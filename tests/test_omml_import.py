from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from dq_questionbank import OmmlFormula, parse_omml_element, read_docx_math

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "omml"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def load_docx(target: Path) -> Path:
    fixture = json.loads(
        (FIXTURE_DIR / "omml-fixture.json").read_text(encoding="utf-8")
    )
    target.write_bytes(base64.b64decode(fixture["docx_base64"]))
    return target


class OmmlImportTests(unittest.TestCase):
    def test_fixture_formulas_reproduce_their_latex_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = load_docx(Path(temporary) / "omml-fixture.docx")
            fixture = json.loads(
                (FIXTURE_DIR / "omml-fixture.json").read_text(encoding="utf-8")
            )

            formulas = read_docx_math(source)

            self.assertEqual(len(fixture["expected"]), len(formulas))
            for expected, formula in zip(fixture["expected"], formulas, strict=True):
                self.assertEqual(expected["latex"], formula.latex)
                self.assertEqual(expected["display"], formula.display)

    def test_display_and_inline_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = load_docx(Path(temporary) / "omml-fixture.docx")
            formulas = read_docx_math(source)

            self.assertFalse(formulas[0].display, "bare m:oMath is inline")
            self.assertTrue(formulas[3].display, "m:oMathPara marks display")

    def test_unsupported_constructs_are_preserved_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = load_docx(Path(temporary) / "omml-fixture.docx")
            formulas = read_docx_math(source)

            bar = formulas[-1]
            self.assertEqual("x", bar.latex, "text is preserved, never dropped")
            self.assertIn("bar", bar.unsupported)

    def test_parse_omml_element_maps_each_construct(self):
        cases = [
            ("<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num>"
             "<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f>", "\\frac{a}{b}"),
            ("<m:sSub><m:e><m:r><m:t>a</m:t></m:r></m:e>"
             "<m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub>", "a_{1}"),
            ("<m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e>"
             "<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>", "x^{2}"),
            ("<m:rad><m:deg><m:r><m:t>3</m:t></m:r></m:deg>"
             "<m:e><m:r><m:t>8</m:t></m:r></m:e></m:rad>", "\\sqrt[3]{8}"),
            ("<m:d><m:dPr><m:begChr m:val=\"[\"/><m:endChr m:val=\"]\"/></m:dPr>"
             "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:d>", "\\left[x\\right]"),
            ("<m:nary><m:naryPr><m:chr m:val=\"∫\"/></m:naryPr>"
             "<m:e><m:r><m:t>f</m:t></m:r></m:e></m:nary>", "\\int f"),
        ]
        for xml, expected in cases:
            with self.subTest(construct=xml.split(">", 1)[0]):
                element = ET.fromstring(
                    f'<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                    f'officeDocument/2006/math">{xml}</m:oMath>'
                )
                formula = parse_omml_element(element)
                self.assertEqual(expected, formula.latex)
                self.assertEqual((), formula.unsupported)

    def test_formula_record_round_trips(self):
        formula = OmmlFormula(latex="\\frac{a}{b}", display=True, unsupported=())
        restored = OmmlFormula(
            latex=formula.latex, display=formula.display, unsupported=formula.unsupported
        )
        self.assertEqual(formula, restored)


if __name__ == "__main__":
    unittest.main()
