# Roadmap

This roadmap follows the public question lifecycle. It describes migration
workstreams, not promises to copy private modules or ship them in one release.
Each batch must use synthetic data and preserve the public/private boundary.

## 1. Foundation

**Status: available**

- Canonical model and JSON Schema
- Validation, migrations, and compatibility fixtures
- JSON, Markdown, LaTeX, and convention-based DOCX adapters
- Stable public API manifest and opt-in plugin discovery
- Atomic filesystem storage and a reviewed read-only SQLite case adapter
- CI, public-tree audit, release gate, and English-language public contract

## 2. Visual workspace

**Status: operational public workspace available in v0.5.0**

- Local-first Question Bank with collection browsing and scoped filters
- Structured text, math, table, choice, answer, and solution rendering
- Focused selected-question Editor Center
- Canonical JSON import, local save, and export
- Paper assembly with deterministic ordering and canonical JSON export
- Collection metrics and deterministic local quality checks with editor handoff
- Next: image-pool editing, interactive table authoring, and richer formula modules

## 3. Import and review

**Status: planned as independent public contracts**

- Source-evidence records and adaptable import profiles
- Candidate sessions that separate extraction from persistence
- Deterministic validation before bounded AI-assisted suggestions
- Human Review Center acceptance and rejection states
- No bundled provider, credential, private prompt, or automatic production write

## 4. Daily question work

**Status: first local-only batch available in v0.5.0**

- Paper and collection assembly is available for the active canonical set
- Field-level Editor Center workflows are available for public canonical fields
- Deterministic quality findings link back to the exact question and field
- Recheck after save without silently rewriting question content
- Synthetic browser fixtures for end-to-end contributor testing

Revision-bound persisted findings and candidate review sessions remain separate
architecture work; the current quality queue is computed locally and does not
claim those contracts.

## 5. Word publishing

**Status: planned; conventional DOCX remains available today**

- Loopback-only Word integration contract
- Refreshable question reference blocks
- Native Word math, images, tables, option layouts, and answer sections
- Visible composition borders that can be hidden for final output
- Explicit compatibility and rollback behavior

## 1.0 readiness

Version 1.0 requires external implementation feedback, a broadened migration
fixture suite, a maintained stable API manifest, documented security and release
governance, and proven upgrade and rollback paths. The repository does not claim
1.0 compatibility before those gates pass.

Contributor-sized work is tracked through the
[`frontend`](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues?q=is%3Aissue+is%3Aopen+label%3Afrontend),
[`storage`](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues?q=is%3Aissue+is%3Aopen+label%3Astorage),
[`import`](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues?q=is%3Aissue+is%3Aopen+label%3Aimport),
[`quality`](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues?q=is%3Aissue+is%3Aopen+label%3Aquality),
[`editor`](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues?q=is%3Aissue+is%3Aopen+label%3Aeditor), and
[`word`](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues?q=is%3Aissue+is%3Aopen+label%3Aword)
labels.

