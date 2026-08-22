from __future__ import annotations

import json
import tempfile
import unittest
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from dq_questionbank import Answer, Choice, Content, ContentBlock, Question, QuestionSet
from dq_questionbank.word_publishing import (
    WordPublisher,
    WordPublishingBridge,
    WordPublishingError,
    build_envelope,
    export_word_publishing,
    extract_managed_blocks,
    question_fingerprint,
    validate_envelope,
    word_macro_source,
)


def _question_set() -> QuestionSet:
    return QuestionSet(
        "synthetic-word",
        "Synthetic Word publishing case",
        [
            Question(
                "q-alpha",
                "single_choice",
                Content(
                    [
                        ContentBlock(type="text", text="Choose the value of "),
                        ContentBlock(type="math", latex="x^2"),
                        ContentBlock(type="table", rows=[["x", "1"], ["x^2", "1"]]),
                    ]
                ),
                choices=[
                    Choice("A", Content.text("1")),
                    Choice("B", Content.text("2")),
                ],
                answer=Answer("choices", ["A"]),
                solution=Content.text("Substitute x = 1."),
            ),
            Question("q-beta", "short_answer", Content.text("State the result.")),
        ],
    )


class WordPublishingTests(unittest.TestCase):
    def test_envelope_validation_fails_closed(self):
        envelope = build_envelope(_question_set())
        validate_envelope(envelope)

        remote = json.loads(json.dumps(envelope))
        remote["service_origin"] = "https://example.test:8766"
        remote["security"]["allowed_origins"] = [remote["service_origin"]]
        with self.assertRaisesRegex(WordPublishingError, "loopback"):
            validate_envelope(remote)

        duplicate = json.loads(json.dumps(envelope))
        duplicate["blocks"].append(dict(duplicate["blocks"][0]))
        with self.assertRaisesRegex(WordPublishingError, "Duplicate"):
            validate_envelope(duplicate)

    def test_refresh_is_ordered_and_stale_blocks_keep_previous_content(self):
        question_set = _question_set()
        envelope = build_envelope(question_set, ["q-beta", "q-alpha"])
        previous = {envelope["blocks"][1]["block_id"]: {"content": "previous block"}}
        envelope["blocks"][1]["question_fingerprint"] = "sha256:" + "0" * 64

        results = WordPublisher(question_set).refresh(envelope, previous)

        self.assertEqual([item.block_id for item in results], ["block-q-beta-001", "block-q-alpha-002"])
        self.assertEqual(results[0].status, "refreshed")
        self.assertEqual(results[1].status, "stale")
        self.assertEqual(results[1].reason, "revision-mismatch")
        self.assertEqual(results[1].content, "previous block")

    def test_missing_question_is_stale_and_compose_final_differ_only_in_affordance(self):
        question_set = _question_set()
        envelope = build_envelope(question_set)
        compose = WordPublisher(question_set).refresh(envelope)[0]
        envelope["mode"] = "final"
        final = WordPublisher(question_set).refresh(envelope)[0]
        self.assertIn("[compose]", compose.content or "")
        self.assertNotIn("[compose]", final.content or "")

        missing = _question_set()
        missing.questions.pop(0)
        result = WordPublisher(missing).refresh(build_envelope(question_set))[0]
        self.assertEqual((result.status, result.reason), ("stale", "missing-question"))

    def test_docx_contains_deterministic_managed_content_controls(self):
        question_set = _question_set()
        envelope = build_envelope(question_set)
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.docx"
            second = Path(temporary) / "second.docx"
            export_word_publishing(question_set, first, envelope)
            export_word_publishing(question_set, second, envelope)
            blocks = extract_managed_blocks(first)
            self.assertEqual(list(blocks), ["block-q-alpha-001", "block-q-beta-002"])
            self.assertEqual(
                blocks["block-q-alpha-001"]["question_fingerprint"],
                question_fingerprint(question_set.questions[0]),
            )
            with ZipFile(first) as package1, ZipFile(second) as package2:
                self.assertEqual(
                    package1.read("word/document.xml"),
                    package2.read("word/document.xml"),
                )
                self.assertIn(b"dqwb:block-q-alpha-001", package1.read("word/document.xml"))

    def test_loopback_bridge_inserts_and_refreshes_without_credentials(self):
        question_set = _question_set()
        bridge = WordPublishingBridge(question_set, port=0)
        bridge.start()
        try:
            request = urllib.request.Request(
                bridge.origin + "/v1/insert",
                data=json.dumps(
                    {"question_id": "q-alpha", "block_id": "word-block-1", "mode": "compose"}
                ).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-DQ-Word-Protocol": "0.2",
                },
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.load(response)
            self.assertEqual(payload["status"], "inserted")
            self.assertEqual(
                payload["block"]["question_fingerprint"],
                question_fingerprint(question_set.questions[0]),
            )
            with urllib.request.urlopen(bridge.origin + "/status", timeout=2) as response:
                self.assertEqual(json.load(response)["credentials"], "never")
        finally:
            bridge.close()

        with self.assertRaisesRegex(WordPublishingError, "loopback"):
            WordPublishingBridge(question_set, "0.0.0.0", 0)

    def test_bundled_macro_has_complete_operations_and_no_remote_execution(self):
        source = word_macro_source()
        for operation in (
            "DQ_InsertReferenceBlock",
            "DQ_CheckBridge",
            "DQ_RefreshCurrentBlock",
            "DQ_RefreshAllBlocks",
            "DQ_ShowComposeBlocks",
            "DQ_RenderFinal",
            "restore-previous-block",
        ):
            self.assertIn(operation, source)
        self.assertIn("http://127.0.0.1:8766", source)
        self.assertNotIn("https://", source)
        self.assertNotIn("Shell(", source)
        self.assertNotIn("WScript", source)
        self.assertNotIn("Authorization", source)


if __name__ == "__main__":
    unittest.main()
