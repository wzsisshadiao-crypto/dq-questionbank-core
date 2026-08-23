# Formula-Image Transcription Candidates

Imported documents sometimes carry formulas as raster images no
deterministic parser can read. The public answer is a **candidate
record** — not bundled OCR. `dq_questionbank.formula_images` defines the
contract:

## Detection

```python
from dq_questionbank import detect_formula_image_candidates

candidates = detect_formula_image_candidates(question)
```

Only image blocks the source pipeline explicitly flagged with
`metadata.formula_image: true` become candidates, and only when the
referenced asset exists and carries a SHA-256 digest. The flag is the
deterministic signal a source adapter sets when it rasterizes a formula;
no OCR engine, external service, or network access is used or required.

A `FormulaImageCandidate` binds:

- `question_id` and `target_field` (the exact block path, e.g.
  `stem.blocks[1]`);
- `asset_id`, `asset_uri`, and `asset_sha256` — the image evidence;
- an empty `latex` slot and `status: "pending"`.

## Human transcription

```python
from dq_questionbank import fill_transcription

filled = fill_transcription(candidate, question, "\\frac{n!}{k!(n-k)!}", "contributor-name")
```

Filling the slot records the contributor as the transcription source
while the image stays attached as evidence. The transcription fails
closed when the asset is missing or its digest changed since detection —
re-run detection and review the new image instead. A candidate can be
transcribed exactly once.

## Intake handoff

The serialized record is a review-item shape: an import profile carries
candidates next to its other bounded proposals, a Review Center renders
the image evidence with an empty transcription input, and the filled
record is the reviewer's decision artifact. Nothing here persists or
approves anything automatically.

The synthetic demonstration fixture (a deterministic 1x1 PNG embedded in
a question block) lives in `tests/fixtures/formula-images/`.
