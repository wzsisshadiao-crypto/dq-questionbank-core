from __future__ import annotations

import json
import unittest
from pathlib import Path

from dq_questionbank import (
    RULESET_VERSION,
    Content,
    ContentBlock,
    QualityFinding,
    QualityJudgment,
    Question,
    StaleFindingError,
    detect_quality_findings,
    field_fingerprint,
    finding_state,
    judge_finding,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "quality" / "findings"


def question_with_stem(stem_blocks, question_id="q-findings-1"):
    return Question(
        question_id,
        "short_answer",
        Content(stem_blocks),
        answer={"kind": "text", "value": "Manual review resolves the finding."},
    )


def mismatch_question():
    return question_with_stem(
        [
            ContentBlock(type="text", text="Consider the malformed interval "),
            ContentBlock(type="math", latex="(x+1]"),
        ]
    )


class FieldFingerprintTests(unittest.TestCase):
    def test_fingerprint_is_deterministic_and_key_order_independent(self):
        first = field_fingerprint({"b": 2, "a": 1})
        second = field_fingerprint({"a": 1, "b": 2})

        self.assertEqual(first, second)

    def test_any_content_change_changes_the_fingerprint(self):
        self.assertNotEqual(
            field_fingerprint({"latex": "(x+1]"}),
            field_fingerprint({"latex": "(x+1)"}),
        )


class DetectionTests(unittest.TestCase):
    def test_detection_binds_finding_to_block_path_and_fingerprint(self):
        findings = detect_quality_findings(mismatch_question())

        self.assertEqual(1, len(findings))
        finding = findings[0]
        self.assertEqual("q-findings-1", finding.question_id)
        self.assertEqual("stem.blocks[1]", finding.target_field)
        self.assertEqual("latex-mismatched-delimiters", finding.rule_id)
        self.assertEqual(RULESET_VERSION, finding.ruleset_version)
        self.assertEqual("error", finding.severity)
        self.assertIsNone(finding.repair)
        (path, fingerprint), = finding.input_fingerprints
        self.assertEqual("stem.blocks[1]", path)
        self.assertEqual(64, len(fingerprint))

    def test_detection_reports_repairable_sources_with_preview_data(self):
        question = question_with_stem(
            [ContentBlock(type="math", latex="sin x + cos x \\frac{1}{2")]
        )
        findings = detect_quality_findings(question)

        self.assertEqual(1, len(findings))
        finding = findings[0]
        self.assertEqual("warning", finding.severity)
        self.assertIsNotNone(finding.repair)
        self.assertEqual("latex-bare-function-names", finding.repair["rule_id"])
        self.assertEqual("\\sin x + \\cos x \\frac{1}{2}", finding.repair["latex"])

    def test_detection_leaves_clean_questions_empty(self):
        question = question_with_stem(
            [ContentBlock(type="math", latex="\\frac{\\sqrt{3}}{x+1}")]
        )

        self.assertEqual([], detect_quality_findings(question))

    def test_detection_covers_solution_and_choice_blocks(self):
        question = Question(
            "q-scope",
            "short_answer",
            Content([ContentBlock(type="math", latex="\\left( x \\right)")]),
            solution=Content([ContentBlock(type="math", latex="2(x+1")]),
        )

        paths = {finding.target_field for finding in detect_quality_findings(question)}
        self.assertEqual({"stem.blocks[0]", "solution.blocks[0]"}, paths)


class StalenessTests(unittest.TestCase):
    def test_finding_is_current_against_unchanged_question(self):
        finding, = detect_quality_findings(mismatch_question())

        self.assertEqual("current", finding_state(finding, mismatch_question()))

    def test_edited_target_field_makes_finding_stale(self):
        finding, = detect_quality_findings(mismatch_question())
        edited = question_with_stem(
            [
                ContentBlock(type="text", text="Consider the malformed interval "),
                ContentBlock(type="math", latex="[x+1)"),
            ]
        )

        self.assertEqual("stale", finding_state(finding, edited))

    def test_changed_question_id_makes_finding_stale(self):
        finding, = detect_quality_findings(mismatch_question())
        other = question_with_stem(
            [
                ContentBlock(type="text", text="Consider the malformed interval "),
                ContentBlock(type="math", latex="(x+1]"),
            ],
            question_id="q-other",
        )

        self.assertEqual("stale", finding_state(finding, other))

    def test_unrelated_field_edit_keeps_finding_current(self):
        finding, = detect_quality_findings(mismatch_question())
        edited = Question(
            "q-findings-1",
            "short_answer",
            Content(
                [
                    ContentBlock(type="text", text="Consider the malformed interval "),
                    ContentBlock(type="math", latex="(x+1]"),
                ]
            ),
            answer={"kind": "text", "value": "An unrelated edit."},
        )

        self.assertEqual("current", finding_state(finding, edited))

    def test_cross_field_finding_stales_when_any_dependency_changes(self):
        question = mismatch_question()
        finding = QualityFinding(
            question_id="q-findings-1",
            target_field="stem.blocks[1]",
            rule_id="hypothetical-cross-field",
            ruleset_version=RULESET_VERSION,
            input_fingerprints=(
                ("stem", field_fingerprint(question.stem.to_dict())),
                ("answer", field_fingerprint(question.answer)),
            ),
            severity="warning",
            explanation="A hypothetical rule that reads both fields.",
        )

        self.assertEqual("current", finding_state(finding, question))
        edited_answer = Question(
            "q-findings-1",
            "short_answer",
            question.stem,
            answer={"kind": "text", "value": "Changed."},
        )
        self.assertEqual("stale", finding_state(finding, edited_answer))

    def test_ruleset_version_mismatch_is_stale(self):
        finding, = detect_quality_findings(mismatch_question())
        older = QualityFinding(
            question_id=finding.question_id,
            target_field=finding.target_field,
            rule_id=finding.rule_id,
            ruleset_version="quality/0",
            input_fingerprints=finding.input_fingerprints,
            severity=finding.severity,
            explanation=finding.explanation,
        )

        self.assertEqual("stale", finding_state(older, mismatch_question()))


class JudgmentTests(unittest.TestCase):
    def test_judging_a_current_finding_records_the_decision(self):
        finding, = detect_quality_findings(mismatch_question())
        judgment = judge_finding(finding, mismatch_question(), "accepted")

        self.assertEqual("accepted", judgment.decision)
        self.assertEqual(finding.fingerprint(), judgment.finding_fingerprint)

    def test_judging_a_stale_finding_fails_closed(self):
        finding, = detect_quality_findings(mismatch_question())
        edited = question_with_stem(
            [
                ContentBlock(type="text", text="Consider the malformed interval "),
                ContentBlock(type="math", latex="[x+1)"),
            ]
        )

        with self.assertRaises(StaleFindingError):
            judge_finding(finding, edited, "rejected")

    def test_unsupported_decision_is_rejected(self):
        finding, = detect_quality_findings(mismatch_question())

        with self.assertRaises(ValueError):
            judge_finding(finding, mismatch_question(), "maybe")


class SerializationTests(unittest.TestCase):
    def test_finding_round_trips_through_its_serialized_form(self):
        finding, = detect_quality_findings(mismatch_question())

        restored = QualityFinding.from_dict(json.loads(json.dumps(finding.to_dict())))

        self.assertEqual(finding, restored)
        self.assertEqual(finding.fingerprint(), restored.fingerprint())

    def test_unknown_finding_field_fails_closed(self):
        payload = detect_quality_findings(mismatch_question())[0].to_dict()
        payload["mystery"] = True

        with self.assertRaises(ValueError):
            QualityFinding.from_dict(payload)

    def test_judgment_round_trips_through_its_serialized_form(self):
        finding, = detect_quality_findings(mismatch_question())
        judgment = judge_finding(finding, mismatch_question(), "rejected")

        restored = QualityJudgment.from_dict(
            json.loads(json.dumps(judgment.to_dict()))
        )

        self.assertEqual(judgment, restored)


class FixtureTests(unittest.TestCase):
    def _load(self, name):
        payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
        question = Question.from_dict(payload["question"])
        finding = QualityFinding.from_dict(payload["finding"])
        return payload, question, finding

    def test_current_fixture_is_current(self):
        payload, question, finding = self._load("current.json")

        self.assertEqual(payload["expected_state"], finding_state(finding, question))

    def test_stale_fixture_is_stale(self):
        payload, question, finding = self._load("stale.json")

        self.assertEqual(payload["expected_state"], finding_state(finding, question))
        with self.assertRaises(StaleFindingError):
            judge_finding(finding, question, "accepted")

    def test_accepted_fixture_round_trips_a_judgment(self):
        payload, question, finding = self._load("accepted.json")

        judgment = judge_finding(finding, question, "accepted")
        self.assertEqual(
            payload["judgment"]["finding_fingerprint"],
            judgment.finding_fingerprint,
        )

    def test_rejected_fixture_round_trips_a_judgment(self):
        payload, question, finding = self._load("rejected.json")

        judgment = judge_finding(finding, question, "rejected")
        self.assertEqual("rejected", judgment.decision)


if __name__ == "__main__":
    unittest.main()
