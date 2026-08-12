# Contributing

Thank you for helping build open infrastructure for educational questions.

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[docx,dev]"
python -m unittest discover -s tests -v
```

Run the full local gate before submitting a pull request:

```bash
python -m ruff check src tests scripts
python -m unittest discover -s tests -v
python scripts/audit_public_tree.py
python -m build
```

## Issues

Search existing issues first. Use a minimal, synthetic example and include the Python version, operating system, input format, expected result, and actual result. Do not upload private or copyrighted question banks.

## Pull requests

- Keep changes focused and explain user impact.
- Add meaningful tests for behavior changes.
- Update documentation and compatibility notes when formats or schema behavior change.
- Do not commit generated databases, logs, credentials, private URLs, or real exam content.
- Use concise imperative commit messages, such as `Preserve image references in Markdown export`.

## Adding an importer or exporter

Implement `QuestionImporter` or `QuestionExporter` from `dq_questionbank.interfaces`, declare a stable `format_name` and `extensions`, and register the adapter in a caller-owned `FormatRegistry`. Built-in formats require focused tests, documented limitations, and deterministic output where practical.

## Extending the schema

Prefer `metadata` for experimental fields. A new required field or changed meaning requires a schema-version proposal, migration guidance, fixtures, and compatibility tests. Never silently reinterpret existing data.

## Compatibility policy

During `0.x`, breaking changes require a minor release and migration notes. Patch releases must remain backward compatible. After `1.0`, incompatible schema or public Python API changes require a major release.

## Copyright and provenance

Contributors must have the right to submit all code and fixtures. Examples should be original, synthetic, public domain, or provided under a compatible license with attribution. Publisher question banks and exam papers are not acceptable fixtures merely because they can be found online.
