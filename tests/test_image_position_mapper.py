from __future__ import annotations

import json
import unittest

from dq_questionbank.image_position_mapper import (
    DEFAULT_FIELD,
    DEFAULT_ROLE,
    IMAGE_PLACEMENT_VERSION,
    REASON_AMBIGUOUS_QUESTION_RANGES,
    REASON_INVALID_RANGE,
    REASON_OUTSIDE_ALL_QUESTIONS,
    REASON_STRADDLES_QUESTION_BOUNDARY,
    ImagePlacement,
    ImagePlacementReport,
    infer_image_placements,
)


def question_range(question_id: str, start: int, end: int) -> dict:
    """Build one ordered, non-overlapping question range record."""
    return {"question_id": question_id, "start_paragraph": start, "end_paragraph": end}


def image(image_id: str, start: int, end: int, page: int | None = None) -> dict:
    """Build one extracted-image record with an inclusive paragraph range."""
    record = {"image_id": image_id, "start_paragraph": start, "end_paragraph": end}
    if page is not None:
        record["page"] = page
    return record


LAYOUT = (
    question_range("q1", 1, 10),
    question_range("q2", 11, 20),
    question_range("q3", 21, 30),
)


def image_ids(report: ImagePlacementReport) -> list[str]:
    """Pull the image ids back out of a report, in placement order."""
    ids = []
    for placement in report.placements:
        found = next(i for i in placement.evidence if i["kind"] == "image-range")
        ids.append(found["image_id"])
    return ids


class ContainmentTests(unittest.TestCase):
    def test_inside_range_maps_with_both_ranges_as_evidence(self):
        report = infer_image_placements((image("fig-1", 4, 6, page=2),), LAYOUT)

        placement = report.placements[0]
        self.assertEqual("q1", placement.question_id)
        self.assertEqual(DEFAULT_FIELD, placement.field)
        self.assertEqual(DEFAULT_ROLE, placement.role)
        self.assertIsNone(placement.reason)
        self.assertTrue(placement.known)

        kinds = [item["kind"] for item in placement.evidence]
        self.assertEqual(["image-range", "question-range"], kinds)
        image_side = placement.evidence[0]
        self.assertEqual("fig-1", image_side["image_id"])
        self.assertEqual(4, image_side["start_paragraph"])
        self.assertEqual(6, image_side["end_paragraph"])
        self.assertEqual(2, image_side["page"])
        question_side = placement.evidence[1]
        self.assertEqual("q1", question_side["question_id"])
        self.assertEqual(1, question_side["start_paragraph"])
        self.assertEqual(10, question_side["end_paragraph"])

    def test_image_at_either_range_edge_is_still_inside(self):
        images = (
            image("edge-start", 1, 1),
            image("edge-end", 10, 10),
            image("edge-later", 21, 25),
        )

        report = infer_image_placements(images, LAYOUT)

        self.assertEqual(
            ("q1", "q1", "q3"),
            tuple(item.question_id for item in report.placements),
        )
        self.assertTrue(all(item.reason is None for item in report.placements))

    def test_page_is_optional_in_image_evidence(self):
        report = infer_image_placements((image("no-page", 2, 3),), LAYOUT)

        record = report.placements[0].evidence[0]
        self.assertNotIn("page", record)


class BoundaryTests(unittest.TestCase):
    def test_straddling_two_questions_is_unknown(self):
        report = infer_image_placements((image("span", 9, 12),), LAYOUT)

        placement = report.placements[0]
        self.assertIsNone(placement.question_id)
        self.assertIsNone(placement.field)
        self.assertIsNone(placement.role)
        self.assertFalse(placement.known)
        self.assertEqual(REASON_STRADDLES_QUESTION_BOUNDARY, placement.reason)
        involved = [
            item["question_id"]
            for item in placement.evidence
            if item["kind"] == "question-range"
        ]
        self.assertEqual(["q1", "q2"], involved)

    def test_partial_overlap_with_one_question_is_unknown(self):
        single = (question_range("only", 1, 20),)

        report = infer_image_placements((image("hang", 15, 22),), single)

        placement = report.placements[0]
        self.assertIsNone(placement.question_id)
        self.assertEqual(REASON_STRADDLES_QUESTION_BOUNDARY, placement.reason)

    def test_shared_edge_paragraph_is_ambiguous_not_guessed(self):
        adjacent = (
            question_range("qa", 1, 10),
            question_range("qb", 10, 20),
        )

        report = infer_image_placements((image("on-edge", 10, 10),), adjacent)

        self.assertEqual(REASON_AMBIGUOUS_QUESTION_RANGES, report.placements[0].reason)
        self.assertIsNone(report.placements[0].question_id)


class UnknownPlacementTests(unittest.TestCase):
    def test_orphan_outside_all_questions_is_unknown(self):
        report = infer_image_placements((image("orphan", 41, 45),), LAYOUT)

        placement = report.placements[0]
        self.assertIsNone(placement.question_id)
        self.assertEqual(REASON_OUTSIDE_ALL_QUESTIONS, placement.reason)
        self.assertEqual(1, len(placement.evidence))
        self.assertEqual("image-range", placement.evidence[0]["kind"])

    def test_invalid_image_range_is_unknown(self):
        report = infer_image_placements((image("backwards", 8, 5),), LAYOUT)

        placement = report.placements[0]
        self.assertIsNone(placement.question_id)
        self.assertEqual(REASON_INVALID_RANGE, placement.reason)

    def test_duplicate_question_ranges_are_ambiguous(self):
        duplicated = (
            question_range("q1", 1, 10),
            question_range("q1-copy", 1, 10),
        )

        report = infer_image_placements((image("dupe-target", 3, 4),), duplicated)

        placement = report.placements[0]
        self.assertIsNone(placement.question_id)
        self.assertEqual(REASON_AMBIGUOUS_QUESTION_RANGES, placement.reason)

    def test_overlapping_question_ranges_are_ambiguous_when_both_cover(self):
        overlapping = (
            question_range("q1", 1, 10),
            question_range("q2", 5, 15),
        )

        report = infer_image_placements((image("covered", 6, 8),), overlapping)

        self.assertEqual(REASON_AMBIGUOUS_QUESTION_RANGES, report.placements[0].reason)


class ReportShapeTests(unittest.TestCase):
    def test_no_images_yields_empty_report(self):
        report = infer_image_placements((), LAYOUT)

        self.assertEqual((), report.placements)
        self.assertEqual({"placements": []}, report.to_dict())

    def test_no_question_ranges_marks_every_image_orphan(self):
        images = (image("a", 1, 2), image("b", 3, 4))

        report = infer_image_placements(images, ())

        self.assertEqual(
            (REASON_OUTSIDE_ALL_QUESTIONS, REASON_OUTSIDE_ALL_QUESTIONS),
            tuple(item.reason for item in report.placements),
        )

    def test_placements_preserve_input_order(self):
        images = (
            image("img-orphan", 40, 41),
            image("img-inside", 12, 13),
            image("img-straddle", 19, 22),
            image("img-invalid", 30, 29),
        )

        report = infer_image_placements(images, LAYOUT)

        self.assertEqual(
            ["img-orphan", "img-inside", "img-straddle", "img-invalid"],
            image_ids(report),
        )
        self.assertEqual(
            (
                REASON_OUTSIDE_ALL_QUESTIONS,
                "q2",
                REASON_STRADDLES_QUESTION_BOUNDARY,
                REASON_INVALID_RANGE,
            ),
            tuple(item.question_id or item.reason for item in report.placements),
        )


class SerializationTests(unittest.TestCase):
    def test_report_round_trips_through_json(self):
        images = (image("keep-1", 2, 3, page=7), image("keep-2", 15, 25))

        report = infer_image_placements(images, LAYOUT)
        payload = json.loads(json.dumps(report.to_dict()))
        restored = ImagePlacementReport.from_dict(payload)

        self.assertEqual(report, restored)
        self.assertEqual("image-placement/1", IMAGE_PLACEMENT_VERSION)

    def test_mapped_placement_round_trips(self):
        report = infer_image_placements((image("rt", 2, 3),), LAYOUT)

        placement = report.placements[0]
        payload = json.loads(json.dumps(placement.to_dict()))
        restored = ImagePlacement.from_dict(payload)

        self.assertEqual(placement, restored)

    def test_unknown_placement_round_trips(self):
        report = infer_image_placements((image("unk", 9, 12),), LAYOUT)

        placement = report.placements[0]
        payload = json.loads(json.dumps(placement.to_dict()))
        restored = ImagePlacement.from_dict(payload)

        self.assertEqual(placement, restored)
        self.assertEqual(REASON_STRADDLES_QUESTION_BOUNDARY, restored.reason)

    def test_placement_rejects_unknown_fields(self):
        report = infer_image_placements((image("mystery", 2, 3),), LAYOUT)

        payload = report.placements[0].to_dict()
        payload["mystery"] = True
        with self.assertRaises(ValueError):
            ImagePlacement.from_dict(payload)

    def test_report_rejects_unknown_fields(self):
        report = infer_image_placements((), LAYOUT)

        payload = report.to_dict()
        payload["mystery"] = True
        with self.assertRaises(ValueError):
            ImagePlacementReport.from_dict(payload)

    def test_reason_requires_missing_question(self):
        report = infer_image_placements((image("ok", 2, 3),), LAYOUT)

        payload = report.placements[0].to_dict()
        payload["reason"] = REASON_OUTSIDE_ALL_QUESTIONS
        with self.assertRaises(ValueError):
            ImagePlacement.from_dict(payload)

    def test_unsupported_reason_fails_closed(self):
        report = infer_image_placements((image("bad", 9, 12),), LAYOUT)

        payload = report.placements[0].to_dict()
        payload["reason"] = "maybe-attached"
        with self.assertRaises(ValueError):
            ImagePlacement.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
