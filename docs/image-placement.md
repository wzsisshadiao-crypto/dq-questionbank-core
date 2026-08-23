# Image Placement Inference

An import pipeline can usually locate an image on the page, but cannot
always prove which question owns it. `dq_questionbank.image_position_mapper`
(merged as part of #90, ruleset version `image-placement/1`) is the pure
inference half of that decision: `infer_image_placements(images,
question_ranges)` returns an `ImagePlacementReport` holding exactly one
placement per input image, in input order.

## The never-guess contract

- A **mapped** placement names the owning `question_id` plus
  `field="stem"` and `role="figure"` - neutral defaults, because
  paragraph ranges alone carry no finer signal - and its `evidence`
  records both the image range and the question range that proves
  containment.
- An **unknown** placement sets `question_id` to `None` and carries
  exactly one machine-readable `reason`. Its evidence still records the
  image range plus every question range involved in the refusal, so a
  reviewer can audit the decision without re-running inference.

The two states are mutually exclusive and enforced on deserialization:
`question_id` is `None` exactly when `reason` is set, an unknown
placement carries no field or role, and a mapped placement requires
both. The report never reorders, drops, or merges images.

## When an image maps

Inputs are small records with inclusive integer paragraph ranges:

- `images`: `{image_id, start_paragraph, end_paragraph}` with an
  optional `page`, preserved into the evidence.
- `question_ranges`: `{question_id, start_paragraph, end_paragraph}`,
  which the caller promises are ordered and non-overlapping. Overlaps
  are still handled - conservatively, as ambiguity.

An image maps when exactly one question range fully contains its range
(`question.start <= image.start` and `image.end <= question.end`). The
bounds are inclusive: an image sitting exactly on either edge paragraph
of the question is inside.

## Unknown reasons

Rules are evaluated per image, first match wins:

| Reason | Meaning |
|---|---|
| `invalid-range` | The image's own range is degenerate (`end < start`); the extraction evidence is corrupt and the image should be re-extracted, not placed |
| `ambiguous-question-ranges` | Two or more question ranges fully contain the image (duplicated or overlapping segmentation) |
| `straddles-question-boundary` | The image touches two or more question ranges, or hangs past the only range it meets |
| `outside-all-questions` | The image meets no question range at all (front matter, headers, gaps between questions) |

Degenerate question ranges (`end < start`) touch nothing and are inert.

## Recipe

```python
from dq_questionbank.image_position_mapper import infer_image_placements

question_ranges = (
    {"question_id": "q1", "start_paragraph": 1, "end_paragraph": 10},
    {"question_id": "q2", "start_paragraph": 11, "end_paragraph": 20},
)
images = (
    {"image_id": "fig-inside", "start_paragraph": 4, "end_paragraph": 6, "page": 2},
    {"image_id": "fig-span", "start_paragraph": 9, "end_paragraph": 12},
)

report = infer_image_placements(images, question_ranges)
for placement in report.placements:
    if placement.known:
        print(placement.question_id, placement.field, placement.role)
    else:
        print(placement.reason)
```

This prints `q1 stem figure` for the contained image and
`straddles-question-boundary` for the image crossing the q1/q2 edge -
the same layout used in `tests/test_image_position_mapper.py`.

## How this feeds import and review

Unknown placements are not failures to discard; they are queue items
for a human. A caller zips placements back onto its images (the i-th
placement decides the i-th image), renders the recorded evidence, and
asks a reviewer to name the owner - after which the ordinary
review-first intake in [import-cases.md](import-cases.md) applies.
Reports and placements round-trip through `to_dict()` / `from_dict()`,
which reject unknown fields, unsupported reasons, and reason/question
combinations that violate the contract above.

Adjacent contracts, for images that already have an owner:

- [asset-repair.md](asset-repair.md) binds evidence when a question's
  raster bytes are wrong or missing;
- [formula-images.md](formula-images.md) queues rasterized formulas for
  human LaTeX transcription.

Both, like this module, refuse to guess and fail closed.
