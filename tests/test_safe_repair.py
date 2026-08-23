from __future__ import annotations

import unittest

from dq_questionbank.models import Content, ContentBlock, Question
from dq_questionbank.quality_findings import QualityFinding, detect_quality_findings
from dq_questionbank.safe_repair import (
    EDITABLE_FIELDS,
    GATE_ALLOW,
    GATE_DENY,
    REASON_ALLOWLIST,
    REASON_MALFORMED,
    REASON_NEW_QUALITY_FINDINGS,
    REASON_NEW_VALIDATION_ERRORS,
    REASON_NO_PROGRESS,
    changed_fields,
    evaluate_repair,
)


def make_question(question_id: str = "q1", latex: str | None = None) -> Question:
    """Build a synthetic single-block or text+math question."""
    blocks = [ContentBlock(type="text", text="Compute the value.")]
    if latex is not None:
        blocks.append(ContentBlock(type="math", latex=latex))
    return Question(id=question_id, type="short_answer", stem=Content(blocks))


def make_finding(question_id: str, target_field: str, rule_id: str) -> QualityFinding:
    """Build a synthetic open finding without running detection."""
    return QualityFinding(
        question_id=question_id,
        target_field=target_field,
        rule_id=rule_id,
        ruleset_version="quality/1",
        input_fingerprints=((target_field, "0" * 64),),
        severity="warning",
        explanation="Synthetic finding for gate tests.",
    )


class SafeRepairGateTests(unittest.TestCase):
    def test_genuine_fix_is_allowed(self):
        original = make_question(latex="sin x + 1")
        findings = detect_quality_findings(original)
        self.assertTrue(findings)

        edited = make_question(latex="\\sin x + 1")

        decision = evaluate_repair(original, edited, findings)

        self.assertEqual(GATE_ALLOW, decision.decision)
        self.assertEqual((), decision.reasons)
        self.assertIn("resolved-findings=1", decision.evidence)

    def test_allowlist_violation_is_denied(self):
        original = make_question()
        edited = make_question(question_id="q2")

        decision = evaluate_repair(original, edited, ())

        self.assertEqual(GATE_DENY, decision.decision)
        self.assertEqual((REASON_ALLOWLIST,), decision.reasons)
        self.assertIn("violations=id", decision.evidence)

    def test_no_progress_edit_is_denied(self):
        original = make_question(latex="sin x + 1")
        findings = detect_quality_findings(original)
        edited = make_question(latex="sin x + 1")
        edited.stem.blocks[0].text = "Compute the value carefully."

        decision = evaluate_repair(original, edited, findings)

        self.assertEqual(GATE_DENY, decision.decision)
        self.assertEqual((REASON_NO_PROGRESS,), decision.reasons)

    def test_declared_no_progress_edit_is_allowed(self):
        original = make_question(latex="sin x + 1")
        findings = detect_quality_findings(original)
        edited = make_question(latex="sin x + 1")
        edited.stem.blocks[0].text = "Compute the value carefully."

        decision = evaluate_repair(
            original, edited, findings, progress_declaration="Wording only."
        )

        self.assertEqual(GATE_ALLOW, decision.decision)
        self.assertIn("progress-declaration=declared", decision.evidence)

    def test_progress_but_new_errors_is_denied(self):
        original = make_question()
        finding = make_finding("q1", "stem.blocks[1]", "latex-demo")
        edited = make_question()
        edited.stem = Content([])  # Empty stem is a semantic validation error.

        decision = evaluate_repair(original, edited, (finding,))

        self.assertEqual(GATE_DENY, decision.decision)
        self.assertEqual((REASON_NEW_VALIDATION_ERRORS,), decision.reasons)

    def test_new_quality_finding_is_denied(self):
        original = make_question()
        edited = make_question(latex="(x+1")  # Mismatched delimiter finding.

        decision = evaluate_repair(original, edited, ())

        self.assertEqual(GATE_DENY, decision.decision)
        self.assertEqual((REASON_NEW_QUALITY_FINDINGS,), decision.reasons)

    def test_malformed_input_fails_closed(self):
        original = make_question()

        decision = evaluate_repair(original, {"id": "not-a-question"}, ())

        self.assertEqual(GATE_DENY, decision.decision)
        self.assertEqual((REASON_MALFORMED,), decision.reasons)

    def test_clean_candidate_edit_has_nothing_to_prove(self):
        original = make_question()
        edited = make_question()
        edited.stem.blocks[0].text = "Reworded prompt."

        decision = evaluate_repair(original, edited, ())

        self.assertEqual(GATE_ALLOW, decision.decision)
        self.assertIn("open-findings=0", decision.evidence)

    def test_changed_fields_uses_canonical_serialization(self):
        original = make_question()
        edited = make_question()
        edited.stem.blocks[0].text = "Reworded prompt."

        self.assertEqual(("stem",), changed_fields(original, edited))
        self.assertEqual((), changed_fields(original, make_question()))

    def test_editable_fields_protect_identity_and_provenance(self):
        protected = {"id", "type", "language", "schema_version", "source", "taxonomy", "assets"}
        self.assertEqual(set(), EDITABLE_FIELDS & protected)


class GateDecisionSerializationTests(unittest.TestCase):
    def test_round_trip(self):
        decision = evaluate_repair(make_question(), make_question())

        restored = type(decision).from_dict(decision.to_dict())

        self.assertEqual(decision, restored)

    def test_from_dict_rejects_unknown_keys(self):
        with self.assertRaises(ValueError):
            type(evaluate_repair(make_question(), make_question())).from_dict(
                {"decision": "allow", "reasons": [], "evidence": [], "extra": 1}
            )


class SafeRepairWiringTests(unittest.TestCase):
    """The gate is the default path inside review_import_session."""

    def test_clean_candidate_edit_still_passes_the_pipeline(self):
        from dq_questionbank import ImportCandidateSession, prepare_import_case

        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))
        candidate = typed.candidates[0]
        edited = {
            **candidate.question,
            "stem": {
                "blocks": [{"type": "text", "text": "Edited: "}]
                + list(candidate.question["stem"]["blocks"])
            },
        }

        reviewed = typed.decide(
            {
                "decisions": [
                    {
                        "question_id": candidate.question_id,
                        "candidate_sha256": candidate.question_sha256,
                        "decision": "accepted",
                        "edited_question": edited,
                    }
                ]
            }
        )

        self.assertEqual("accepted", reviewed.candidates[0].decision)
        self.assertEqual(2, reviewed.candidates[0].revision)

    def test_edit_introducing_a_new_finding_is_denied_at_review_time(self):
        from dq_questionbank import (
            ImportBundleError,
            ImportCandidateSession,
            prepare_import_case,
        )

        typed = ImportCandidateSession.from_session(prepare_import_case("manual-web"))
        candidate = typed.candidates[0]
        edited = {
            **candidate.question,
            "stem": {
                "blocks": list(candidate.question["stem"]["blocks"])
                + [{"type": "math", "latex": "(x+1"}]
            },
        }

        with self.assertRaises(ImportBundleError) as raised:
            typed.decide(
                {
                    "decisions": [
                        {
                            "question_id": candidate.question_id,
                            "candidate_sha256": candidate.question_sha256,
                            "decision": "accepted",
                            "edited_question": edited,
                        }
                    ]
                }
            )

        self.assertIn("safe-repair gate", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
