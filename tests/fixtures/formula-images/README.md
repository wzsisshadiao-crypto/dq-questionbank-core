# Formula-image candidate fixtures

This original synthetic specimen backs the formula-image candidate
records (`dq_questionbank.formula_images`). The fixture carries:

- a deterministic 1x1 grayscale PNG, base64-encoded inside
  `formula-image-question.json`, with its SHA-256 pinned alongside;
- a canonical question whose stem embeds that image through an asset
  reference, with `metadata.formula_image: true` marking it as a formula
  raster that needs human transcription.

Expected behavior, executed by `tests/test_formula_images.py`:

- detection binds the block path (`stem.blocks[1]`), the asset reference
  and digest, and an empty `latex` slot;
- filling the slot records the contributor while the image stays
  attached as evidence;
- a missing asset or a changed digest fails closed;
- unflagged images and digest-less assets never become candidates.

No OCR engine, external service, or network access is involved. See
`provenance.json` for redistribution status.
