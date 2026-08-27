from __future__ import annotations

import unittest

from dq_questionbank.word_macro_id import (
    WordMacroIdMemory,
    expand_question_spec,
    is_year_token,
    normalize_spec_separators,
)


class WordMacroIdExpandTests(unittest.TestCase):
    def _fresh_memory(self) -> WordMacroIdMemory:
        return WordMacroIdMemory()

    def test_full_scenario_chain(self) -> None:
        memory = self._fresh_memory()
        self.assertEqual(
            "KY_SX_SF_AH_2026_4",
            expand_question_spec("KY_SX_SF_AH_2026_4", memory),
        )
        self.assertEqual("KY_SX_SF_AH_2026_6", expand_question_spec("6", memory))
        self.assertEqual(
            "KY_SX_SF_AH_2024_5", expand_question_spec("2024_5", memory)
        )
        self.assertEqual(
            "KY_SX_SF_DLLG_2025_6",
            expand_question_spec("DLLG_2025_6", memory),
        )
        self.assertEqual(
            "KY_SX_GD_DLLG_2024_5", expand_question_spec("GD_2024_5", memory)
        )
        self.assertEqual(
            "KY_SX_GD_THU_2025_3",
            expand_question_spec("GD_THU_2025_3", memory),
        )
        self.assertEqual(
            "KY_SX_GD_THU_2025_9", expand_question_spec("_9", memory)
        )

    def test_spaces_act_as_underscores(self) -> None:
        memory = self._fresh_memory()
        self.assertEqual(
            "KY_SX_SF_SEU_2025_4",
            expand_question_spec("KY SX SF SEU 2025 4", memory),
        )
        self.assertEqual("KY_SX_SF_SEU_2025_6", expand_question_spec("6", memory))
        self.assertEqual(
            "KY_SX_SF_SEU_2024_5",
            expand_question_spec("SEU 2024 5", memory),
        )
        second = self._fresh_memory()
        self.assertEqual(
            "KY_SX_SF_AH_2026_4",
            expand_question_spec("KY  SX  SF AH\t2026 4", second),
        )
        self.assertEqual(
            "KY_SX_SF_AH_2026_7,KY_SX_SF_AH_2026_8",
            expand_question_spec("7, 8", second),
        )

    def test_reserved_tokens_never_become_school(self) -> None:
        memory = self._fresh_memory()
        expand_question_spec("KY_SX_SF_AH_2026_4", memory)
        self.assertIsNone(expand_question_spec("KY_2024_5", memory))
        self.assertIsNone(expand_question_spec("SX_2024_5", memory))

    def test_invalid_short_forms_rejected(self) -> None:
        memory = self._fresh_memory()
        expand_question_spec("KY_SX_SF_AH_2026_4", memory)
        self.assertIsNone(expand_question_spec("ABC", memory))
        self.assertIsNone(expand_question_spec("99999_5", memory))
        self.assertIsNone(expand_question_spec("123_2024_5", memory))

    def test_malformed_full_ids_rejected_without_memory_damage(self) -> None:
        memory = self._fresh_memory()
        expand_question_spec("KY_SX_SF_AH_2026_4", memory)
        self.assertIsNone(expand_question_spec("KY_SX_SF_AH_2026", memory))
        self.assertIsNone(expand_question_spec("KY_SX_SF_SF_2026_4", memory))
        self.assertIsNone(expand_question_spec("KY_SX_SF_AH_2026_x", memory))
        # the rejected forms must not have overwritten the seeded memory
        self.assertEqual(("SF", "AH", "2026"),
                         (memory.subject, memory.school, memory.year))


    def test_comma_batch_expands_every_element(self) -> None:
        memory = self._fresh_memory()
        expand_question_spec("KY_SX_GD_THU_2025_3", memory)
        self.assertEqual(
            "KY_SX_GD_THU_2025_7,KY_SX_GD_THU_2025_8,KY_SX_GD_THU_2025_9",
            expand_question_spec("7,8,9", memory),
        )

    def test_comma_batch_is_all_or_nothing(self) -> None:
        memory = self._fresh_memory()
        expand_question_spec("KY_SX_SF_AH_2026_4", memory)
        self.assertIsNone(expand_question_spec("5, ABC", memory))

    def test_legacy_range_passthrough(self) -> None:
        memory = self._fresh_memory()
        self.assertEqual(
            "GZ_SX_100-GZ_SX_105",
            expand_question_spec("GZ_SX_100-GZ_SX_105", memory),
        )

    def test_empty_input_returns_none(self) -> None:
        self.assertIsNone(expand_question_spec("", self._fresh_memory()))
        self.assertIsNone(expand_question_spec("   ", self._fresh_memory()))


class WordMacroIdHelpersTests(unittest.TestCase):
    def test_normalize_spec_separators(self) -> None:
        self.assertEqual("KY_SX_SF_AH_2026_4",
                         normalize_spec_separators("KY SX SF AH 2026 4"))
        self.assertEqual("7,8,9", normalize_spec_separators("7, 8, 9"))
        self.assertEqual("7,8,9", normalize_spec_separators("7 ,8 ,9"))
        self.assertEqual("a_b", normalize_spec_separators("a__b"))

    def test_is_year_token(self) -> None:
        self.assertTrue(is_year_token("2026"))
        self.assertTrue(is_year_token("1998"))
        self.assertFalse(is_year_token("1899"))
        self.assertFalse(is_year_token("26600"))
        self.assertFalse(is_year_token("202a"))


if __name__ == "__main__":
    unittest.main()
