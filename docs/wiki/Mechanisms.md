# Mechanisms

How each engine actually works. The structure of the system is on
[Architecture](Architecture.md); this page is the principle behind every
mechanism, with pointers into the repository-owned reference docs.

## 1. Canonical model and schema versioning

Everything exchanges one recursive model: `QuestionSet -> Question ->
Content -> ContentBlock` (`text`, `math`, `image`, `table`, `code`, `line_break`).
`to_dict()`/`from_dict()` round-trip deterministically and **fail closed on
unknown fields**, so a newer file never silently drops meaning in an older
reader. Two schema versions ship (`1.0`, `1.1`); `validate_with_schema()`
dispatches on the declared version and rejects unknown ones. Upgrades go
through registered migrations in `migration.py` that never mutate input and
refuse ambiguous paths. Details: [question schema](../question-schema.md),
[schema migrations](../schema-migrations.md).

## 2. Atomic storage adapters

`FilesystemStorageAdapter.save()` writes to a temporary file in the target
directory and `os.replace()`s it into place - a reader never observes a
half-written set, and a crash cannot corrupt the previous version.
`SqliteStorageAdapter` mirrors the same contract over stdlib `sqlite3`.
Load paths validate before returning. Details:
[filesystem storage](../filesystem-storage.md), [SQLite](../sqlite-storage.md).

## 3. Review-first intake

Importing never writes a question bank. The pipeline has four explicit
states, each bound to the SHA-256 digest of the previous artifact: a
**bundle** (raw records + evidence) becomes **candidates** (proposed
canonical questions), a human records **decisions** (accept/reject per
question and per field), and only then **export** produces a reviewed
QuestionSet. Digest binding means a decision made against version A of a
candidate cannot be silently applied to version B. Five synthetic routes
(manual web, web AI, coding agent, PDF coding agent, OMML exam) install as
runnable cases; custom sources plug in at the bundle boundary. Details:
[import cases](../import-cases.md), [product workflow](../product-workflow.md).

## 4. Quality findings and safe repair

`detect_quality_findings(question)` is deterministic, local, and produces
findings that carry severity, a decision state, and a fingerprint of the
exact field they refer to. Repairs are gated: `safe_repair.py` only applies
transforms that provably cannot lose content (fail closed when ambiguous),
and re-scanning after a save invalidates findings whose field fingerprint
changed - a fixed finding disappears, an untouched finding survives.
Batch scanning runs as resumable runs with checkpoints. Details:
[quality findings](../quality-findings.md), [scan runs](../scan-runs.md),
[arithmetic checks](../arithmetic-checks.md).

## 5. The three LaTeX engines

- **Repair** (`latex_repair.py`) fixes *broken* sources - missing braces,
  bare function names, delimiter spacing - fail-closed.
- **Normalization** (`latex_normalize.py`) is *graded*: rules marked
  `autoFixable` apply mechanically; `reviewReason` rules can only ever
  produce a proposal. The code path for review rules structurally cannot
  write to the result. Details: [LaTeX normalization](../latex-normalization.md).
- **Compatibility** (`latex_compat.py`) restores exact PDF-transcription
  degradation footprints (`$A$，$\quad B$` rejoined only when both sides are
  relations; bare `dx` goes upright only inside integrals).

## 6. Word publishing envelope

`word-publish` writes a Word document whose questions live inside **managed
content controls**, each stamped with a `question_fingerprint` - a digest of
the canonical question content. The exported **envelope** JSON records what
was published. Later, `word-serve` (loopback, credential-free) plus the
generated VBA macro (`word-macro`) let Word **refresh** those blocks: the
macro asks the local server for the current question; if the fingerprint
matches, the block is rebuilt with native Word math (OMML); if the question
is missing or the fingerprint differs, the existing block is left untouched.
Publishing is therefore refreshable, not a one-way export. Details:
[Word publishing envelope](../word-publishing-envelope.md).

## 7. PDF toolchain and coding-agent gates

For synthetic vector PDFs the toolchain is deterministic and side-effect
free: **split** (marker-based chunking with locator lines), **worksets**
(batching with recall proof), **skeletons** (human-finishable transcriptions).
After an agent transcribes, three pure gates protect the volume:
`pdf_postflight` scans staged candidates (continuity, identity fields,
content hashes, manifest digests), `pdf_metadata` requires whole-volume
paper metadata agreement, and `pdf_identity` decides whether a runtime job
id really belongs to a canonical paper tag. Details:
[PDF toolchain](../pdf-toolchain.md),
[coding-agent import contract](../coding-agent-import.md).

## 8. Coding-agent work file

An agent with workspace access edits exactly one JSON work file
(`coding-agent-workfile/v1`). The contract is enforced in code: required
text fields, unique numbering, a three-state transcription loop
(`pending -> transcribed -> needs_review -> transcribed`), and **forbidden
pipeline-owned fields** (`question_id`, evidence bindings, runtime
bookkeeping) so transcription can never override identity. Writes are
atomic; reads tolerate an editor-added BOM.

## 9. Determinism and the verification stack

Identical inputs must produce identical outputs everywhere: JSON
serialization is canonical, import cases regenerate byte-identically (CI
runs the regeneration and diffs), the stable public API has a checked-in
manifest (`docs/public-api-manifest.json`) so any signature change is a
reviewed event, and the Wiki export is verified against its source
manifest. A weekly benchmark run enforces ceiling budgets
(`benchmarks/workspace-budgets.json`) so performance regressions surface as
CI failures instead of user complaints.

## 10. Security posture

Loopback-only servers; no bundled credentials, prompts, or providers; the
public-tree audit scans every checked-in text file for secret shapes and
rejects private data directories, production databases, and unreviewed
binaries; question asset paths cannot traverse outside their set. Reporting
follows [SECURITY.md](../../SECURITY.md).

Back to [Architecture](Architecture.md) or [Home](Home.md).

