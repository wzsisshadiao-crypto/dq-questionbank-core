from __future__ import annotations

import unittest
from pathlib import Path

from dq_questionbank import validate_with_schema
from dq_questionbank.models import Question
from dq_questionbank.pdf_skeleton import (
    PDF_SKELETON_VERSION,
    STATUS_NEEDS_HUMAN,
    STATUS_PREFILLED,
    TranscriptionSkeleton,
    build_skeleton,
    to_question_payload,
)
from dq_questionbank.pdf_splitter import (
    PDF_SPLIT_VERSION,
    PdfChunk,
    PdfSplitResult,
    PdfTextLine,
    extract_text_lines,
    split_pdf_questions,
)
from dq_questionbank.pdf_workset import (
    PDF_WORKSET_VERSION,
    RecallReport,
    WorksetPlan,
    build_worksets,
    verify_recall,
)


def write_pdf(pages: list[list[str]]) -> bytes:
    """Write a minimal, deterministic multi-page PDF (no dependencies)."""
    page_ids = [4 + 2 * index for index in range(len(pages))]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            "<< /Type /Pages /Kids ["
            + " ".join(f"{pid} 0 R" for pid in page_ids)
            + f"] /Count {len(pages)} >>"
        ).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for page_number, lines in enumerate(pages):
        page_id = page_ids[page_number]
        content_id = page_id + 1
        stream_parts = ["BT /F1 11 Tf 14 TL 50 780 Td"]
        for line in lines:
            safe = line.replace("\\", "").replace("(", "").replace(")", "")
            stream_parts.append(f"({safe}) Tj T*")
        stream_parts.append("ET")
        stream = "\n".join(stream_parts).encode("latin-1")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode()
        )
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_at).encode()
        + b"\n%%EOF\n"
    )
    return bytes(out)


def _chunk(key: str, *texts: str) -> PdfChunk:
    return PdfChunk(
        question_key=key,
        marker_text=texts[0],
        lines=tuple(
            PdfTextLine(page=1, index=position, text=text)
            for position, text in enumerate(texts)
        ),
    )



BUNDLED_PDF = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "dq_questionbank"
    / "data"
    / "import_cases"
    / "pdf-table"
    / "structured-worksheet.pdf"
).read_bytes()


class PdfSplitterTests(unittest.TestCase):
    def test_extracts_lines_with_pages_in_order(self):
        pdf = write_pdf(
            [["Alpha page one.", "Beta page one."], ["Gamma page two."]]
        )
        lines = extract_text_lines(pdf)
        self.assertEqual(
            [(line.page, line.index, line.text) for line in lines],
            [
                (1, 0, "Alpha page one."),
                (1, 1, "Beta page one."),
                (2, 0, "Gamma page two."),
            ],
        )

    def test_split_chunks_at_markers_with_header(self):
        pdf = write_pdf(
            [
                [
                    "Synthetic Paper",
                    "Question A-01. First stem line.",
                    "Answer key: 4",
                    "Question A-02. Second stem line.",
                    "Worked solution: doubled.",
                ]
            ]
        )
        result = split_pdf_questions(pdf)
        keys = [chunk.question_key for chunk in result.chunks]
        self.assertEqual(keys, ["A-01", "A-02"])
        self.assertEqual(
            [line.text for line in result.header_lines], ["Synthetic Paper"]
        )
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.chunks[0].lines[-1].text, "Answer key: 4")

    def test_chunks_span_pages_and_keep_locators(self):
        pdf = write_pdf(
            [
                ["Question B-01. starts here."],
                ["continues on page two.", "Question B-02. next."],
            ]
        )
        result = split_pdf_questions(pdf)
        keys = [chunk.question_key for chunk in result.chunks]
        self.assertEqual(keys, ["B-01", "B-02"])
        self.assertEqual(
            [(line.page, line.index) for line in result.chunks[0].lines],
            [(1, 0), (2, 0)],
        )

    def test_mid_sentence_reference_never_splits(self):
        pdf = write_pdf(
            [
                [
                    "Question C-01. Recall Question C-99 above.",
                    "See also Question C-98 in the notes.",
                ]
            ]
        )
        result = split_pdf_questions(pdf)
        self.assertEqual([chunk.question_key for chunk in result.chunks], ["C-01"])

    def test_split_is_deterministic(self):
        pdf = write_pdf([["Question D-01. one.", "Question D-02. two."]])
        self.assertEqual(split_pdf_questions(pdf), split_pdf_questions(pdf))

    def test_no_markers_yields_reason_and_keeps_header(self):
        pdf = write_pdf([["Just a title.", "No questions here."]])
        result = split_pdf_questions(pdf)
        self.assertEqual(result.chunks, ())
        self.assertIn("no-question-markers", result.reasons)
        self.assertEqual(len(result.header_lines), 2)

    def test_empty_bytes_yield_reason(self):
        self.assertIn("empty-pdf", split_pdf_questions(b"").reasons)

    def test_split_round_trip_and_unknown_key_rejection(self):
        pdf = write_pdf([["Question E-01. one.", "Answer key: 7"]])
        payload = split_pdf_questions(pdf).to_dict()
        self.assertEqual(PdfSplitResult.from_dict(payload).to_dict(), payload)
        payload["note"] = "extra"
        with self.assertRaises(ValueError):
            PdfSplitResult.from_dict(payload)


class PdfWorksetTests(unittest.TestCase):
    def test_worksets_batch_in_document_order(self):
        pdf = write_pdf([[f"Question F-0{i}. stem." for i in range(1, 6)]])
        plan = build_worksets(split_pdf_questions(pdf), batch_size=2)
        self.assertEqual(
            [workset.question_keys for workset in plan.worksets],
            [("F-01", "F-02"), ("F-03", "F-04"), ("F-05",)],
        )
        self.assertEqual(plan.worksets[0].workset_id, "ws-1")

    def test_empty_split_yields_reason(self):
        plan = build_worksets(PdfSplitResult((), (), ("no-question-markers",)))
        self.assertEqual(plan.worksets, ())
        self.assertIn("nothing-to-batch", plan.reasons)

    def test_invalid_batch_size_is_rejected(self):
        with self.assertRaises(ValueError):
            build_worksets(PdfSplitResult((), (), ()), batch_size=0)

    def test_recall_ok_with_exact_expected_count(self):
        pdf = write_pdf([["Question G-01. one.", "Question G-02. two."]])
        report = verify_recall(split_pdf_questions(pdf), expected_count=2)
        self.assertTrue(report.ok)
        self.assertEqual(report.duplicate_keys, ())
        self.assertEqual(report.missing_count, 0)

    def test_recall_reports_missing_questions(self):
        pdf = write_pdf([["Question H-01. one."]])
        report = verify_recall(split_pdf_questions(pdf), expected_count=3)
        self.assertFalse(report.ok)
        self.assertEqual(report.missing_count, 2)

    def test_recall_reports_double_claims(self):
        result = PdfSplitResult((_chunk("I-01", "a"), _chunk("I-01", "b")), (), ())
        report = verify_recall(result, expected_count=1)
        self.assertFalse(report.ok)
        self.assertEqual(report.duplicate_keys, ("I-01",))

    def test_negative_expected_count_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_recall(PdfSplitResult((), (), ()), expected_count=-1)

    def test_plan_and_report_round_trips(self):
        split = split_pdf_questions(write_pdf([["Question J-01. one."]]))
        plan = build_worksets(split)
        self.assertEqual(WorksetPlan.from_dict(plan.to_dict()), plan)
        report = verify_recall(split, 1)
        self.assertEqual(RecallReport.from_dict(report.to_dict()), report)


class PdfSkeletonTests(unittest.TestCase):
    def test_slots_prefill_from_deterministic_prefixes(self):
        chunk = _chunk(
            "K-01",
            "Question K-01. Read the table.",
            "Outcome | Count",
            "Answer key: 8 outcomes in total.",
            "Worked solution: Add the column.",
        )
        skeleton = build_skeleton(chunk)
        by_field = [(slot.field, slot.status) for slot in skeleton.slots]
        self.assertEqual(
            by_field,
            [
                ("stem", STATUS_PREFILLED),
                ("stem", STATUS_PREFILLED),
                ("answer", STATUS_PREFILLED),
                ("solution", STATUS_PREFILLED),
            ],
        )
        self.assertEqual(skeleton.slots[2].value, "8 outcomes in total.")
        self.assertEqual(skeleton.slots[3].value, "Add the column.")
        self.assertEqual((skeleton.slots[0].page, skeleton.slots[0].index), (1, 0))

    def test_missing_fields_become_needs_human_slots(self):
        skeleton = build_skeleton(_chunk("L-01", "Question L-01. Stem only."))
        statuses = {
            slot.field: slot.status
            for slot in skeleton.slots
            if slot.field != "stem"
        }
        self.assertEqual(
            statuses, {"answer": STATUS_NEEDS_HUMAN, "solution": STATUS_NEEDS_HUMAN}
        )

    def test_payload_maps_onto_canonical_question(self):
        chunk = _chunk(
            "M-01",
            "Question M-01. Compute.",
            "Answer key: 42",
            "Worked solution: Directly.",
        )
        payload = to_question_payload(build_skeleton(chunk))
        question = Question.from_dict(payload)
        self.assertEqual(question.id, "M-01")
        self.assertEqual(question.type, "short_answer")
        self.assertEqual(question.answer.value, "42")
        self.assertEqual(question.solution.blocks[0].text, "Directly.")
        document = {
            "schema_version": "1.0",
            "id": "skeletons",
            "language": "en",
            "title": "Skeletons",
            "questions": [payload],
        }
        self.assertEqual(validate_with_schema(document), [])
        self.assertEqual(Question.from_dict(payload).to_dict(), payload)

    def test_partial_payload_when_fields_are_unfilled(self):
        skeleton = build_skeleton(_chunk("N-01", "Question N-01. Stem only."))
        payload = to_question_payload(skeleton)
        self.assertNotIn("answer", payload)
        self.assertNotIn("solution", payload)
        document = {
            "schema_version": "1.0",
            "id": "skeletons",
            "language": "en",
            "title": "Skeletons",
            "questions": [payload],
        }
        self.assertEqual(validate_with_schema(document), [])

    def test_skeleton_round_trip_and_unknown_key_rejection(self):
        skeleton = build_skeleton(_chunk("O-01", "Question O-01. One."))
        payload = skeleton.to_dict()
        self.assertEqual(TranscriptionSkeleton.from_dict(payload), skeleton)
        payload["note"] = "extra"
        with self.assertRaises(ValueError):
            TranscriptionSkeleton.from_dict(payload)

    def test_versions_are_stable(self):
        self.assertEqual(PDF_SPLIT_VERSION, "pdf-split/1")
        self.assertEqual(PDF_WORKSET_VERSION, "pdf-workset/1")
        self.assertEqual(PDF_SKELETON_VERSION, "pdf-skeleton/1")


class PdfToolchainPipelineTests(unittest.TestCase):
    def test_full_pipeline_over_bundled_synthetic_fixture(self):
        split = split_pdf_questions(BUNDLED_PDF)
        self.assertEqual([chunk.question_key for chunk in split.chunks], ["T-01"])
        report = verify_recall(split, expected_count=1)
        self.assertTrue(report.ok)
        plan = build_worksets(split, batch_size=3)
        self.assertEqual(plan.worksets[0].question_keys, ("T-01",))
        skeleton = build_skeleton(split.chunks[0])
        answers = [
            slot.value
            for slot in skeleton.slots
            if slot.field == "answer" and slot.status == STATUS_PREFILLED
        ]
        self.assertEqual(answers, ["8 outcomes in total."])
        payload = to_question_payload(skeleton)
        document = {
            "schema_version": "1.0",
            "id": "skeletons",
            "language": "en",
            "title": "Skeletons",
            "questions": [payload],
        }
        self.assertEqual(validate_with_schema(document), [])
        self.assertIn("sum_{k=0}^{n}", payload["stem"]["blocks"][2]["text"])

    def test_pipeline_refuses_unsplit_pdf(self):
        pdf = write_pdf([["A plain document with no markers."]])
        split = split_pdf_questions(pdf)
        self.assertFalse(verify_recall(split, expected_count=1).ok)
        self.assertIn("nothing-to-batch", build_worksets(split).reasons)


if __name__ == "__main__":
    unittest.main()
