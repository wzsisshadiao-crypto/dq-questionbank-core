# Exporters

Exporters render a validated `QuestionSet` without reading private storage.

## Built-in exporters

- JSON is the canonical representation.
- Markdown favors readable review and deterministic generated-file import.
- LaTeX emits a standalone article and machine-readable comment markers.
- DOCX emits visible question, choice, answer, solution, and hint labels and embeds safe local images when available.

## Asset handling

An exporter receives an optional `assets_base`. Relative asset URIs are resolved underneath that directory. Absolute paths and traversal are rejected by validation; remote assets are represented but not downloaded.

## Fidelity

Semantic fidelity and visual fidelity are separate. JSON preserves the canonical model. Human document formats preserve documented fields but may not preserve pagination, fonts, arbitrary source styles, or unsupported embedded objects.

