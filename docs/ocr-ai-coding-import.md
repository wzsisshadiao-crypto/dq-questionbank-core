# OCR + AI Coding Import: the Full Delivery Path

This guide teaches the complete production path for turning a scanned or
PDF/Word paper into reviewed bank questions:

```text
paper.pdf / paper.docx
   1. OCR pass            external OCR API -> page.md (draft text)
   2. first import        coding agent imports from the markdown draft
   3. self cross-check    the model re-reads page images against its import
   4. independent review  a SEPARATE checker thread/agent re-verifies
   5. inbox registration  batch delivered to the review inbox, anchored
   6. human + transfer    review center verdicts, then register into storage
```

Every stage has a public module behind it; nothing here needs the private
application.

## 1. OCR pass (external, optional for native PDFs/DOCX)

Run your OCR provider against page images and export **markdown drafts**
(`page.md`) next to the evidence. Keep the rendered page images - they are
the authority, the markdown is only a typing aid. For native DOCX use the
[OMML import](omml-import.md) path instead; for the repository's synthetic
vector PDFs use the [PDF toolchain](pdf-toolchain.md) (split -> workset ->
skeleton), which needs no OCR at all.

## 2. First import by the coding agent

The agent transcribes each question into a work file governed by
[coding-agent-workfile/v1](coding-agent-import.md): it may edit only the
text fields and the `work_status` loop
(`pending_transcription -> transcribed / needs_review`). Identity fields
(`question_id`, evidence bindings) are pipeline-owned and forbidden in the
file - `validate_work_file()` rejects them.

```python
from dq_questionbank.coding_agent_workfile import (
    validate_work_file, transition_work_status, WORK_STATUS_TRANSCRIBED,
)

findings = validate_work_file(payload)      # contract violations
payload = transition_work_status(payload, "3.2", WORK_STATUS_TRANSCRIBED)
```

Deterministic repairs run next so the agent never hand-fixes what a rule
can fix: `latex_compat` (degraded relation pairs, upright differentials),
`latex_repair` (broken sources), `latex_normalize` (graded cleaning).

## 3. Self cross-check against model OCR ability

With the evidence page images open, the agent (or a second call to your
model) re-reads each formula and compares against the imported LaTeX. This
is a **read-only** pass: disagreements set `work_status = needs_review`
with a `work_note` naming the page and the doubt - never a silent edit.

## 4. Independent checker thread

The cross-checked batch goes to a **completely independent** reviewer
(different session/process, no shared memory with the importer) that sees
only the staged files:

```python
from dq_questionbank.pdf_postflight import scan_candidate_dir

report = scan_candidate_dir(staged_dir)   # numbering, identity, hashes
assert report["ok"], report["findings"]
```

The scan is pure: numbering continuity from `q01.json`, no duplicates,
required identity fields, declared-vs-computed content hashes, and
manifest digest agreement. Quality runs
([scan-runs](scan-runs.md)) add deterministic findings on top.

## 5. Inbox registration (the review gate)

The verified batch is **delivered** to the AI-import inbox
(`ai-inbox-batch/v1`, `dq_questionbank.import_inbox`):

```python
from dq_questionbank.import_inbox import register_batch, verify_receipt

record = register_batch(batch_json, "inbox/AH_2026_JOB/questions")
assert record["status"] == "registered", record["findings"]
```

Registration rules (all enforced in code):

- the **receiver** computes the manifest SHA-256 over the question files -
  a digest declared by the delivering channel is never trusted;
- any blocking finding (missing/undeclared file, bad names, unknown
  verdicts) leaves the batch `blocked` - it cannot reach review or storage;
- a successful registration returns a `confirmation_digest` anchored to
  `batch_id + manifest`.

## 6. Human review and transfer

Reviewers record per-question verdicts on the batch record
(`passed` / `fixed` / `rejected`). Only then, immediately before writing
into storage, the anchor is verified again:

```python
receipt = verify_receipt(record, "registered/AH_2026_JOB/questions")
assert receipt["verified"]   # tamper or drift after registration fails here
```

`verified == False` means the questions changed after registration - the
batch must go back to review. A verified receipt plus all-terminal verdicts
is the only state from which transfer into a `QuestionSet` (and storage) is
allowed; after transfer the batch moves to a terminal status.

## Try it now

- Runnable end-to-end synthetic routes: `dq intake cases` and
  `dq intake run coding-pdf -o workspace/coding-pdf`.
- LaTeX rules and edge-case locking: [latex-regression.md](latex-regression.md).
- Contract internals: [coding-agent-import.md](coding-agent-import.md),
  [pdf-toolchain.md](pdf-toolchain.md), [import-cases.md](import-cases.md).
