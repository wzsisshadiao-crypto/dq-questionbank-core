from __future__ import annotations

import unittest

from dq_questionbank.latex_compat import (
    DEGRADED_PAIR_STATS_KEY,
    DIFFERENTIAL_STATS_KEY,
    is_relation_expression,
    normalize_integral_differentials,
    restore_degraded_relation_pairs,
)


class RestoreDegradedRelationPairsTests(unittest.TestCase):
    def test_real_degraded_pairs_are_restored(self) -> None:
        stats: dict = {}
        text = (
            r"transform $u=\xi+\eta$，$\quad v=\xi-\eta$，"
            r"$\qquad w=\xi\eta$."
        )
        restored = restore_degraded_relation_pairs(text, stats)
        self.assertEqual(
            r"transform $u=\xi+\eta$，$v=\xi-\eta$，$w=\xi\eta$.", restored
        )
        self.assertEqual(2, stats[DEGRADED_PAIR_STATS_KEY])

    def test_qquad_and_leading_spaces(self) -> None:
        self.assertEqual(
            r"$a=\frac{1}{2}$，$b=\frac{3}{2}$",
            restore_degraded_relation_pairs(
                r"$a=\frac{1}{2}$，$\qquad   b=\frac{3}{2}$"
            ),
        )

    def test_non_relation_shapes_are_untouched(self) -> None:
        shapes = (
            r"plain $A$，$\quad B$.",
            r"coords $(x,y)$，$\quad (u,v)$",
            r"range $[a,b]$，$\qquad (c,d)$.",
            r"argument $f(x,y)$，$\quad g(a,b)$.",
            r"$P$，$\quad Q$",
        )
        for shape in shapes:
            self.assertEqual(shape, restore_degraded_relation_pairs(shape))

    def test_already_clean_pairs_are_idempotent(self) -> None:
        clean = r"clean $a=1$，$b=2$ stays."
        self.assertEqual(clean, restore_degraded_relation_pairs(clean))

    def test_plain_text_passes_through(self) -> None:
        self.assertEqual(
            "no math here", restore_degraded_relation_pairs("no math here")
        )


class IsRelationExpressionTests(unittest.TestCase):
    def test_operands_around_a_relation(self) -> None:
        self.assertTrue(is_relation_expression(r"u=\xi+\eta"))
        self.assertTrue(is_relation_expression(r"a \le b"))
        self.assertFalse(is_relation_expression("(x,y)"))
        self.assertFalse(is_relation_expression("[a,b]"))
        self.assertFalse(is_relation_expression("f(x,y)"))
        self.assertFalse(is_relation_expression("=5"))
        self.assertFalse(is_relation_expression(""))


class NormalizeIntegralDifferentialsTests(unittest.TestCase):
    def test_bare_differential_inside_integral(self) -> None:
        self.assertEqual(
            r"$\int_0^1 x\,\mathrm dx$",
            normalize_integral_differentials(r"$\int_0^1 x\,dx$"),
        )

    def test_double_integral_and_greek_differentials(self) -> None:
        self.assertEqual(
            r"$\iint_D f(x,y)\,\mathrm dx\,\mathrm dy$",
            normalize_integral_differentials(
                r"$\iint_D f(x,y)\,dx\,dy$"
            ),
        )
        self.assertEqual(
            r"$\int \varphi(\theta)\,\mathrm d\theta$",
            normalize_integral_differentials(r"$\int \varphi(\theta)\,d\theta$"),
        )

    def test_already_upright_differential_untouched(self) -> None:
        self.assertEqual(
            r"$\int_0^1 x\,\mathrm dx$",
            normalize_integral_differentials(r"$\int_0^1 x\,\mathrm dx$"),
        )

    def test_non_integral_math_untouched(self) -> None:
        self.assertEqual(
            r"$\frac{dy}{dx}$",
            normalize_integral_differentials(r"$\frac{dy}{dx}$"),
        )

    def test_plain_text_untouched(self) -> None:
        self.assertEqual(
            "derivative dx notation",
            normalize_integral_differentials("derivative dx notation"),
        )

    def test_stats_counting(self) -> None:
        stats: dict = {}
        normalize_integral_differentials(
            r"$\int_0^1 x\,dx$ and $\iint_D f\,dx\,dy$", stats
        )
        self.assertEqual(3, stats[DIFFERENTIAL_STATS_KEY])


if __name__ == "__main__":
    unittest.main()
