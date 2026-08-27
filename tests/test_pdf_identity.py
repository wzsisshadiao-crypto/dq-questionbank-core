from __future__ import annotations

import unittest

from dq_questionbank.pdf_identity import job_matches_tag, normalize_import_tag


class NormalizeImportTagTests(unittest.TestCase):
    def test_glued_and_separated_forms_agree(self) -> None:
        self.assertEqual("AH_2026", normalize_import_tag("AH2026"))
        self.assertEqual("AH_2026", normalize_import_tag("ah_2026"))
        self.assertEqual("AH_2026", normalize_import_tag("ah 2026"))
        self.assertEqual("AH_2026", normalize_import_tag("AH-2026".replace("-", " ")))

    def test_runs_collapse_and_edges_trim(self) -> None:
        self.assertEqual("ZS_2024", normalize_import_tag("__zs__2024__"))
        self.assertEqual("DLLG_2025", normalize_import_tag("DLLG2025"))
        self.assertEqual("", normalize_import_tag(""))
        self.assertEqual("", normalize_import_tag("   "))


class JobMatchesTagTests(unittest.TestCase):
    def test_exact_match_after_normalization(self) -> None:
        self.assertTrue(job_matches_tag("AH_2026", "AH2026"))
        self.assertTrue(job_matches_tag("AH2026", "ah_2026"))

    def test_known_runtime_namespaces_match(self) -> None:
        for job in (
            "AH2026_JOB",
            "AH2026_BATCH",
            "AH2026_RUN",
            "AH2026_PDFREG",
            "AH2026_NEWLOGIC",
            "AH2026_W1",
            "AH2026_20260825_W3",
        ):
            self.assertTrue(job_matches_tag(job, "AH2026"), job)

    def test_unknown_suffixes_never_match(self) -> None:
        self.assertFalse(job_matches_tag("AH2026_XYZ", "AH2026"))
        self.assertFalse(job_matches_tag("AH2026B_EXTRA", "AH2026"))

    def test_other_tags_prefix_never_matches(self) -> None:
        # AH2027 is a different paper, not a runtime namespace of AH2026
        self.assertFalse(job_matches_tag("AH2027_JOB", "AH2026"))
        self.assertFalse(job_matches_tag("AH_2026_V2", "AH_2026"))

    def test_empty_tag_never_matches(self) -> None:
        self.assertFalse(job_matches_tag("", ""))
        self.assertFalse(job_matches_tag("AH2026", ""))


if __name__ == "__main__":
    unittest.main()
