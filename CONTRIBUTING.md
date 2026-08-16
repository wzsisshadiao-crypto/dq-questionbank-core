# Contributing

Thank you for helping build open infrastructure for educational questions.

You do not need access to the private application to contribute. Public APIs,
synthetic fixtures, expected behavior, and compatibility requirements are
defined and tested in this repository.

## Where to start

- Browse issues labeled [`good first issue`](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).
- Improve synthetic examples, tests, and user documentation.
- Build adapters for documented format or storage interfaces.
- Help migrate generic frontend, import, review, editor, quality, or Word
  publishing workflows without copying private code or data.
- Update workspace screenshots following the [visual workspace screenshot workflow](docs/visual-workspace-screenshot-workflow.md).

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

## Updating the workspace screenshot

If you change the visual workspace intentionally, follow
[`docs/visual-workspace-screenshot-workflow.md`](docs/visual-workspace-screenshot-workflow.md)
to capture and update the README workspace screenshot and social-preview image
using only the bundled synthetic case. Never capture private questions,
production databases, credentials, or private application screenshots.

## Issues

Search existing issues first. Use a minimal, synthetic example and include the Python version, operating system, input format, expected result, and actual result. Do not upload private or copyrighted question banks.

## Pull requests

- Keep changes focused and explain user impact.
- Add meaningful tests for behavior changes.
- Update documentation and compatibility notes when formats or schema behavior change.
- Do not commit generated databases, logs, credentials, private URLs, or real exam content.
- The reviewed bundled synthetic case at
  `src/dq_questionbank_local/data/synthetic-case.sqlite3` is the only currently
  allowlisted SQLite artifact. New generated databases remain prohibited.
- Use concise imperative commit messages, such as `Preserve image references in Markdown export`.

## Language policy

The maintained public API, CLI, browser playground, documentation, issue
templates, release notes, and Wiki source are English-only. This is an
intentional product boundary, not a restriction on multilingual question data.
Submit English changes to the normative documentation. Community translations
may live independently when they identify the English upstream version and do
not become a competing specification. See
[`docs/language-policy.md`](docs/language-policy.md).

## Adding an importer or exporter

Implement `QuestionImporter` or `QuestionExporter` from `dq_questionbank.interfaces`, declare a stable `format_name` and `extensions`, and register the adapter in a caller-owned `FormatRegistry`. Built-in formats require focused tests, documented limitations, and deterministic output where practical.

## Extending the schema

Prefer `metadata` for experimental fields. A new required field or changed meaning requires a schema-version proposal, migration guidance, fixtures, and compatibility tests. Never silently reinterpret existing data.

## Compatibility policy

During `0.x`, breaking changes require a minor release and migration notes. Patch releases must remain backward compatible. After `1.0`, incompatible schema or public Python API changes require a major release.

## Copyright and provenance

Contributors must have the right to submit all code and fixtures. Examples should be original, synthetic, public domain, or provided under a compatible license with attribution. Publisher question banks and exam papers are not acceptable fixtures merely because they can be found online.
