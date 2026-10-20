from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank.models import QuestionSet
from dq_questionbank.validation import validate_question_set, validate_with_schema

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "examples" / "licensed" / "cemc-2020-pascal"
SAMPLE_PATH = SAMPLE_DIR / "questions.json"
PROVENANCE_PATH = SAMPLE_DIR / "provenance.json"


class LicensedExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
        self.provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))

    def test_sample_is_valid_and_small(self):
        question_set = QuestionSet.from_dict(self.payload)
        self.assertEqual(validate_question_set(question_set), [])
        self.assertEqual(validate_with_schema(self.payload), [])
        self.assertEqual(len(question_set.questions), 3)

    def test_every_question_has_stable_attribution(self):
        expected_locators = {"Question 2", "Question 3", "Question 6"}
        sources = [question["source"] for question in self.payload["questions"]]
        self.assertEqual({source["locator"] for source in sources}, expected_locators)
        for source in sources:
            self.assertEqual(source["license"], "CC-BY-NC-4.0")
            self.assertEqual(source["year"], 2020)
            self.assertTrue(source["uri"].startswith("https://cemc.uwaterloo.ca/"))
            self.assertIn("University of Waterloo", source["author"])
            self.assertIn("CC BY-NC 4.0", source["attribution"])

    def test_provenance_and_disclaimer_are_explicit(self):
        self.assertEqual(self.provenance["license"], "CC-BY-NC-4.0")
        self.assertEqual(self.provenance["locators"], ["Question 2", "Question 3", "Question 6"])
        self.assertRegex(self.provenance["source_pdf_sha256"], r"^[0-9a-f]{64}$")
        readme = (SAMPLE_DIR / "README.md").read_text(encoding="utf-8")
        license_notice = (SAMPLE_DIR / "LICENSE.md").read_text(encoding="utf-8")
        self.assertIn("not affiliated", readme)
        self.assertIn("CC BY-NC 4.0", readme)
        self.assertIn("not covered by the repository's Apache-2.0 license", license_notice)


if __name__ == "__main__":
    unittest.main()
