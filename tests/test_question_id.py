from __future__ import annotations

import unittest

from dq_questionbank.question_id import (
    allocate_question_id,
    allocate_set_id,
    normalize_preferred_id,
)


class QuestionIdAllocationTests(unittest.TestCase):
    def test_fresh_allocation_uses_the_default_base(self):
        self.assertEqual("question-1", allocate_question_id([]))
        self.assertEqual("set-1", allocate_set_id([]))

    def test_fresh_allocation_probes_past_occupied_slots(self):
        existing = ["question-1", "question-2"]

        self.assertEqual("question-3", allocate_question_id(existing))

    def test_preferred_id_is_honored_when_free(self):
        self.assertEqual(
            "algebra-basics", allocate_question_id([], preferred="Algebra Basics")
        )
        self.assertEqual("final-exam", allocate_set_id(["set-1"], preferred="Final Exam"))

    def test_preferred_id_collision_uses_bounded_suffixing(self):
        existing = ["algebra-basics", "algebra-basics-2"]

        self.assertEqual("algebra-basics-3", allocate_question_id(existing, "algebra-basics"))

    def test_allocation_is_deterministic(self):
        existing = ["question-1"]

        self.assertEqual(
            allocate_question_id(existing, "Worksheet 1"),
            allocate_question_id(existing, "Worksheet 1"),
        )

    def test_normalization_lowercases_trims_and_collapses(self):
        self.assertEqual("mixed-case-id", normalize_preferred_id("  Mixed   CASE  id "))
        self.assertEqual("drops-unsafe", normalize_preferred_id("drops!@# unsafe?"))
        self.assertEqual("", normalize_preferred_id("   !@#   "))
        self.assertEqual("", normalize_preferred_id(None))

    def test_exhausting_the_suffix_bound_fails_closed(self):
        existing = [f"question-{n}" for n in range(1, 100)] + ["question"]

        with self.assertRaises(ValueError):
            allocate_question_id(existing)

    def test_set_and_question_namespaces_are_independent(self):
        self.assertEqual("set-1", allocate_set_id(["question-1"]))
        self.assertEqual("question-1", allocate_question_id(["set-1"]))


if __name__ == "__main__":
    unittest.main()
