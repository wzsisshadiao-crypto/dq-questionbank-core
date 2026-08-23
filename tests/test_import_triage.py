from __future__ import annotations

import unittest

from dq_questionbank.import_triage import (
    DECISION_FULL_REDO,
    DECISION_NEEDS_HUMAN,
    DECISION_PATCH,
    TriageDecision,
    triage_candidate,
)


def make_question():
    return {
        "id": "synthetic-triage-001",
        "type": "single_choice",
        "stem": {
            "blocks": [
                {"type": "text", "text": "Estimate the join size."},
                {"type": "math", "latex": "\\sigma_{c}(R) \\bowtie S"},
            ]
        },
        "answer": {"blocks": [{"type": "text", "text": "About 1,200 rows."}]},
        "solution": {
            "blocks": [
                {"type": "text", "text": "Apply the selectivity first."},
                {"type": "math", "latex": "\\frac{|R|}{10} \\cdot |S|"},
            ]
        },
        "choices": [
            {"content": {"blocks": [{"type": "text", "text": "1,200 rows."}]}},
            {"content": {"blocks": [{"type": "text", "text": "12,000 rows."}]}},
        ],
        "source": {"title": "Synthetic triage fixtures"},
        "metadata": {"origin": "synthetic"},
    }


def make_finding(severity="error", target_field="stem.blocks[1]"):
    return {
        "rule_id": "latex/unbalanced-delimiters",
        "severity": severity,
        "target_field": target_field,
    }


class ImportTriageDecisionTests(unittest.TestCase):
    def test_clean_candidate_patches_with_no_findings(self):
        decision = triage_candidate({"question": make_question(), "route": "manual-web"})

        self.assertEqual(DECISION_PATCH, decision.decision)
        self.assertEqual(("no-findings",), decision.reasons)
        self.assertIn("error-findings=0", decision.evidence)
        self.assertIn("route=manual-web", decision.evidence)

    def test_single_block_error_finding_stays_a_patch(self):
        decision = triage_candidate(
            {
                "question": make_question(),
                "findings": [make_finding(target_field="stem.blocks[1]")],
            }
        )

        self.assertEqual(DECISION_PATCH, decision.decision)
        self.assertEqual(("bounded-single-field-findings",), decision.reasons)
        self.assertIn("error-findings=1", decision.evidence)
        self.assertIn("fields=stem.blocks", decision.evidence)

    def test_two_errors_in_one_field_family_stay_a_patch(self):
        decision = triage_candidate(
            {
                "question": make_question(),
                "findings": [
                    make_finding(target_field="solution.blocks[0]"),
                    make_finding(target_field="solution.blocks[1]"),
                ],
            }
        )

        self.assertEqual(DECISION_PATCH, decision.decision)
        self.assertEqual(("bounded-single-field-findings",), decision.reasons)
        self.assertIn("error-findings=2", decision.evidence)
        self.assertIn("fields=solution.blocks", decision.evidence)

    def test_three_errors_across_stem_and_solution_force_full_redo(self):
        decision = triage_candidate(
            {
                "question": make_question(),
                "findings": [
                    make_finding(target_field="stem.blocks[1]"),
                    make_finding(target_field="solution.blocks[0]"),
                    make_finding(target_field="solution.blocks[1]"),
                ],
            }
        )

        self.assertEqual(DECISION_FULL_REDO, decision.decision)
        self.assertEqual(("widespread-findings",), decision.reasons)
        self.assertIn("error-findings=3", decision.evidence)
        self.assertIn("fields=solution.blocks,stem.blocks", decision.evidence)

    def test_two_errors_across_stem_and_choices_force_full_redo(self):
        decision = triage_candidate(
            {
                "question": make_question(),
                "findings": [
                    make_finding(target_field="stem.blocks[1]"),
                    make_finding(target_field="choices[0].content"),
                ],
            }
        )

        self.assertEqual(DECISION_FULL_REDO, decision.decision)
        self.assertEqual(("widespread-findings",), decision.reasons)

    def test_missing_question_is_malformed(self):
        decision = triage_candidate({"findings": []})

        self.assertEqual(DECISION_NEEDS_HUMAN, decision.decision)
        self.assertEqual(("malformed-candidate",), decision.reasons)
        self.assertIn("question=missing", decision.evidence)

    def test_empty_candidate_dict_is_needs_human(self):
        decision = triage_candidate({})

        self.assertEqual(DECISION_NEEDS_HUMAN, decision.decision)
        self.assertEqual(("malformed-candidate",), decision.reasons)

    def test_empty_question_payload_is_ambiguous(self):
        decision = triage_candidate({"question": {}, "findings": []})

        self.assertEqual(DECISION_NEEDS_HUMAN, decision.decision)
        self.assertEqual(("ambiguous-candidate",), decision.reasons)
        self.assertIn("question=empty", decision.evidence)

    def test_missing_findings_with_diagnostics_is_ambiguous(self):
        decision = triage_candidate(
            {"question": make_question(), "diagnostics": ["parser-warned"]}
        )

        self.assertEqual(DECISION_NEEDS_HUMAN, decision.decision)
        self.assertEqual(("ambiguous-candidate",), decision.reasons)
        self.assertIn("findings=missing", decision.evidence)
        self.assertIn("diagnostics=present", decision.evidence)

    def test_unsupported_severity_fails_closed_to_needs_human(self):
        decision = triage_candidate(
            {
                "question": make_question(),
                "findings": [make_finding(severity="fatal")],
            }
        )

        self.assertEqual(DECISION_NEEDS_HUMAN, decision.decision)
        self.assertEqual(("ambiguous-candidate",), decision.reasons)

    def test_warning_only_findings_stay_with_the_human(self):
        decision = triage_candidate(
            {
                "question": make_question(),
                "findings": [make_finding(severity="warning")],
            }
        )

        self.assertEqual(DECISION_NEEDS_HUMAN, decision.decision)
        self.assertEqual(("ambiguous-candidate",), decision.reasons)
        self.assertIn("warning-findings=1", decision.evidence)

    def test_grading_is_deterministic_for_identical_candidates(self):
        candidate = {
            "question": make_question(),
            "findings": [make_finding(target_field="stem.blocks[1]")],
            "route": "omml-import",
        }

        self.assertEqual(triage_candidate(candidate), triage_candidate(candidate))


class TriageDecisionSerializationTests(unittest.TestCase):
    def test_round_trip_preserves_the_decision(self):
        decision = triage_candidate(
            {
                "question": make_question(),
                "findings": [
                    make_finding(target_field="stem.blocks[1]"),
                    make_finding(target_field="solution.blocks[0]"),
                    make_finding(target_field="solution.blocks[1]"),
                ],
            }
        )

        self.assertEqual(decision, TriageDecision.from_dict(decision.to_dict()))

    def test_from_dict_rejects_unknown_fields(self):
        payload = triage_candidate({"question": make_question()}).to_dict()
        payload["confidence"] = "0.9"

        with self.assertRaises(ValueError):
            TriageDecision.from_dict(payload)

    def test_from_dict_rejects_unsupported_decisions(self):
        payload = {"decision": "maybe", "reasons": [], "evidence": []}

        with self.assertRaises(ValueError):
            TriageDecision.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
