# Exporters

Exporters render a validated `QuestionSet` without reading private storage.

## Built-in exporters

- JSON is the canonical representation.
- Markdown favors readable review and deterministic generated-file import.
- LaTeX emits a standalone article and machine-readable comment markers.
- DOCX emits visible question, choice, answer, solution, and hint labels and embeds safe local images when available.
- Managed Word publishing emits revision-bound rich-text content controls and
  includes a loopback-only bridge plus an auditable VBA client for explicit
  insert and refresh operations.

Use `dq word-publish`, `dq word-macro`, and `dq word-serve` for the managed Word
path. Its envelope, stale behavior, rollback rules, security boundary, and
compatibility limits are documented in
[Word Publishing](word-publishing-envelope.md).

## Asset handling

An exporter receives an optional `assets_base`. Relative asset URIs are resolved underneath that directory. Absolute paths and traversal are rejected by validation; remote assets are represented but not downloaded.

## Fidelity

Semantic fidelity and visual fidelity are separate. JSON preserves the canonical model. Human document formats preserve documented fields but may not preserve pagination, fonts, arbitrary source styles, or unsupported embedded objects.

