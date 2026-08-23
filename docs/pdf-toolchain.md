# PDF Toolchain for Synthetic PDFs

Importing PDFs is the hardest intake route: real papers arrive as opaque
binary blobs. This toolchain (merged as part of #89) does not attempt to
understand them. It turns the repository's deterministic, library-free
synthetic vector PDFs into auditable per-question chunks, then into
transcription skeletons a human finishes into canonical questions.

Three pure modules, three stable version markers:

| Module | Version | Stage |
|---|---|---|
| `dq_questionbank.pdf_splitter` | `pdf-split/1` | Split a PDF into per-question chunks |
| `dq_questionbank.pdf_workset` | `pdf-workset/1` | Batch chunks and prove recall |
| `dq_questionbank.pdf_skeleton` | `pdf-skeleton/1` | Build human-finishable skeletons |

Every stage is deterministic and side-effect free: identical bytes and
marker pattern always produce identical chunks. Results round-trip
through `to_dict()` / `from_dict()`; deserialization fails closed on
unknown fields, and split, workset-plan, and skeleton results also
reject unsupported version markers.

## Stage 1 - split

`extract_text_lines(pdf_bytes)` reads uncompressed latin-1 content
streams page by page and walks the `(text) Tj T*` line pattern,
returning `PdfTextLine(page, index, text)` records in document order.
It never decompresses, renders, or guesses.

`split_pdf_questions(pdf_bytes, marker_pattern=r"Question ([A-Z]+-\d+)")`
starts a chunk at each text line that **starts with** the pattern (one
capture group names the question key) and runs to the next marker or
the end of the document, across pages:

- Mid-sentence references such as `Recall Question C-99 above.` never
  split, because only line starts match.
- Lines before the first marker become `header_lines` (titles,
  instructions) instead of a phantom question.
- Every chunk keeps the `page` and `index` locator of each line it owns.

## Stage 2 - batch and prove recall

`build_worksets(split_result, batch_size=3)` groups chunk keys into
ordered worksets `ws-1`, `ws-2`, ... of at most `batch_size` keys, in
document order, so workset 1 always holds the first questions. An empty
split yields an empty plan with one canonical reason instead of a
misleading empty batch.

`verify_recall(split_result, expected_count=None)` proves nothing was
lost. `expected_count` is the number the paper itself claims; the report
counts distinct found keys, lists `duplicate_keys` (keys claimed by more
than one chunk, sorted), and computes `missing_count` as the shortfall
against the expectation. `ok` is true only when there are no duplicates
and, when an expectation is given, the distinct count equals it. Without
an expectation the report still proves the no-double-claim half.

## Stage 3 - skeleton

`build_skeleton(chunk)` bridges raw chunks to the canonical model.
Every chunk line becomes exactly one pre-filled slot carrying its
verbatim value and page/index locator:

- lines starting `Answer key:` or `Worked solution:` become `answer` or
  `solution` slots with the prefix stripped;
- every other line - including `" | "`-joined table rows - stays a
  `stem` slot, kept verbatim.

Fields the chunk never mentions each get one `needs_human` slot, so
nothing is silently dropped and no value is ever invented.

`to_question_payload(skeleton)` projects the finished skeleton onto the
[question schema](question-schema.md): `id` from the question key, type
`short_answer`, ordered text blocks for the stem, a `text`-kind answer,
and one solution text block. `needs_human` slots contribute nothing -
the payload validates as a canonical question but is intentionally
partial until a human fills the empty slots.

## Recipe

Run against the checked-in synthetic fixture; the printed expectations
are the ones `tests/test_pdf_toolchain.py` asserts:

```python
from pathlib import Path

from dq_questionbank.pdf_skeleton import build_skeleton, to_question_payload
from dq_questionbank.pdf_splitter import split_pdf_questions
from dq_questionbank.pdf_workset import build_worksets, verify_recall

pdf = (
    Path("src") / "dq_questionbank" / "data" / "import_cases"
    / "pdf-table" / "structured-worksheet.pdf"
).read_bytes()

split = split_pdf_questions(pdf)
print([chunk.question_key for chunk in split.chunks])  # ['T-01']

recall = verify_recall(split, expected_count=1)
print(recall.ok, recall.missing_count, recall.duplicate_keys)  # True 0 ()

plan = build_worksets(split, batch_size=3)
print(plan.worksets[0].question_keys)  # ('T-01',)

payload = to_question_payload(build_skeleton(split.chunks[0]))
print(payload["id"], payload["type"])  # T-01 short_answer
print(payload["answer"]["value"])  # 8 outcomes in total.
```

The structured stem survives intact: the payload's ordered text blocks
carry the table rows and the `sum_{k=0}^{n}` formula line exactly as
they appear in the fixture. The `pdf-table` case in
[import-cases.md](import-cases.md) shows the full review flow behind
such a source.

## Refusal reasons

A PDF the extractor cannot honestly split yields no chunks, exactly one
canonical reason, and any header lines it did read:

| Reason | Stage | Meaning |
|---|---|---|
| `empty-pdf` | split | The bytes are blank or whitespace only |
| `no-text-lines` | split | No stream matched the `(text) Tj T*` line pattern |
| `no-question-markers` | split | Lines were read, but none starts with the marker pattern |
| `nothing-to-batch` | worksets | There are no chunks to group |

Refusals are data, not exceptions: a marker-less PDF fails recall
verification and batching with these reasons instead of producing
half-parsed chunks.

## Boundary

This toolchain covers synthetic vector PDFs only - the deterministic
uncompressed latin-1 format emitted by `scripts/build_import_cases.py`
and used by the checked-in fixtures. It performs no decompression,
rendering, OCR, or layout inference, so a compressed or scanned PDF
fails honestly with `no-text-lines` or `no-question-markers` rather
than yielding wrong questions. Importing real or copyrighted papers is
out of scope for this repository; see
[../OPEN_SOURCE_BOUNDARY.md](../OPEN_SOURCE_BOUNDARY.md).
