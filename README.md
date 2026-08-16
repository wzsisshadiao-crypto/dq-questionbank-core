# DQ QuestionBank Core

[![CI](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/actions/workflows/ci.yml/badge.svg)](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Release](https://img.shields.io/badge/release-v0.2.1-informational)](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/releases)

Open infrastructure for structured educational questions.

DQ QuestionBank Core is a database-neutral Python library, CLI, and local-first visual application for importing, validating, converting, editing, and exchanging educational questions. Its versioned canonical model supports multilingual text, LaTeX math, images, tables, answer types, source provenance, taxonomy references, and composite questions.

This repository is an independent open-core extraction. It contains no production question bank, user data, private database, commercial workflow, or built-in AI provider.

## Why it exists

Question banks often become inseparable from one database schema, editor, document format, or AI service. This project provides a small interchange core that can sit between those systems:

```text
JSON / Markdown / LaTeX / DOCX
                |
                v
       Importer interface
                |
                v
      Canonical Question Model
                |
        Validation / adapters
                |
                v
       Exporter interface
                |
                v
JSON / Markdown / LaTeX / DOCX
```

## Features

- Versioned, JSON-serializable Question Schema (`1.0`)
- Single choice, multiple choice, true/false, fill-blank, short-answer, essay, and composite questions
- Rich content blocks for text, LaTeX math, images, tables, code, and line breaks
- Asset integrity metadata and safe relative-path validation
- Source attribution, taxonomy references, tags, difficulty, hints, solutions, and extensions
- Deterministic JSON, Markdown, and generated-LaTeX round trips
- Convention-based DOCX import/export with image extraction
- `QuestionImporter`, `QuestionExporter`, `StorageAdapter`, and `AIProvider` interfaces
- Reference local filesystem storage with atomic canonical JSON writes
- English-language CLI, lightweight playground, and complete visual local workspace
- Reviewed read-only SQLite case adapter and bundled synthetic database case
- No database, frontend framework, or AI provider lock-in

## Visual quick start

Python 3.10 or newer is the only requirement for a downloaded source archive:

```bash
python run.py
```

The command starts a loopback-only server, creates an ignored local workspace,
and opens `http://127.0.0.1:8766`. Choose **Open database case** to view the
bundled SQLite case with its questions, choices, answers, and solutions. Import,
edit, save, and export operations stay on the local computer.

To offer another independently reviewed case:

```bash
python run.py --case-database ./downloaded-case.sqlite3
```

See [`docs/database-case.md`](docs/database-case.md) for the supported schema and
mandatory publication review.

## Library installation

From a clone:

```bash
python -m venv .venv
python -m pip install -e ".[docx]"
```

For development:

```bash
python -m pip install -e ".[docx,dev]"
```

Python 3.10, 3.11, and 3.12 are the supported versions.

## Core CLI quick start

Validate the synthetic sample:

```bash
dq validate examples/sample_questions.json
```

Convert canonical JSON to Markdown or LaTeX:

```bash
dq convert examples/sample_questions.json --output-format markdown -o questions.md
dq convert examples/sample_questions.json --output-format latex -o questions.tex
```

Import a DOCX document:

```bash
dq import exam.docx -o questions.json --assets-dir imported_assets
```

Launch the lightweight, English-language canonical JSON playground:

```bash
dq serve
```

Then open `http://127.0.0.1:8765`. The playground processes JSON in the browser and does not upload content.

## Basic library usage

```python
from pathlib import Path

from dq_questionbank.registry import default_registry
from dq_questionbank.validation import validate_question_set

registry = default_registry()
question_set = registry.importer("json").load(Path("questions.json"))
issues = validate_question_set(question_set)

if not issues:
    registry.exporter("markdown").dump(question_set, Path("questions.md"))
```

## Question Schema example

```json
{
  "schema_version": "1.0",
  "id": "math-001",
  "type": "single_choice",
  "language": "en",
  "subject": "Mathematics",
  "stem": {
    "blocks": [
      { "type": "text", "text": "Solve " },
      { "type": "math", "latex": "x + 3 = 7" }
    ]
  },
  "choices": [
    { "id": "A", "content": { "blocks": [{ "type": "text", "text": "3" }] } },
    { "id": "B", "content": { "blocks": [{ "type": "text", "text": "4" }] } }
  ],
  "answer": { "kind": "choice", "value": "B" }
}
```

The normative JSON Schema is at [`schema/question-set.schema.json`](schema/question-set.schema.json). Design notes are in [`docs/question-schema.md`](docs/question-schema.md).

Installed applications can load the same schema with `dq_questionbank.load_schema()`.

## Import and export behavior

| Format | Import | Export | Round-trip level |
|---|---:|---:|---|
| JSON | Yes | Yes | Canonical and deterministic |
| Markdown | Yes | Yes | Canonical for generated files |
| LaTeX | Yes | Yes | Canonical for generated files; basic `enumerate` fallback |
| DOCX | Yes | Yes | Core fields for the documented convention; formatting is best effort |

Human document formats are not lossless containers for every source-specific feature. Generated Markdown and LaTeX include machine-readable markers. DOCX intentionally uses visible labels and extracts embedded images. See [`docs/compatibility.md`](docs/compatibility.md).

## Architecture

- `models.py`: canonical, recursive data model
- `validation.py`: structural and safety rules (plus unified `validate_with_schema()`)
- `exceptions.py`: catchable error hierarchy (`QuestionBankError` and subtypes)
- `migration.py`: schema version migration framework
- `interfaces.py`: extension contracts
- `storage.py`: reference local filesystem storage adapter
- `registry.py`: built-in format discovery with protocol enforcement
- `formats/`: JSON, Markdown, LaTeX, and DOCX adapters
- `cli.py`: thin command wrapper over the library
- `web/`: static local playground; no server-side data storage
- `dq_questionbank_local/`: visual workspace, HTTP API, and reviewed case adapter

See [`OPEN_SOURCE_BOUNDARY.md`](OPEN_SOURCE_BOUNDARY.md) for the public/private boundary and [`docs/oss-architecture-proposal.md`](docs/oss-architecture-proposal.md) for design rationale.

## Development

```bash
python -m unittest discover -s tests -v
python -m ruff check src tests scripts run.py
python -m build
python scripts/audit_public_tree.py
python scripts/check_docs.py
```

The test suite covers model serialization, schema conformance, validation, unsafe asset paths, CLI behavior, format round trips, DOCX conversion, composite questions, formulas, documentation links, English-only public interface, both browser applications, SQLite case safety, and the exception hierarchy.

## Compatibility

Python 3.10-3.12. See [`docs/compatibility.md`](docs/compatibility.md) for format-specific notes,
[`docs/public-api.md`](docs/public-api.md) for the stable Python API, and
[`docs/filesystem-storage.md`](docs/filesystem-storage.md) for the local reference adapter.

## Language policy

English is the single normative language for the public API, CLI, playground,
documentation, and repository-maintained Wiki. This keeps one reviewable public
contract; it does not restrict multilingual question content. See
[`docs/language-policy.md`](docs/language-policy.md).

## Roadmap

See [`docs/roadmap.md`](docs/roadmap.md).

## Contributing and security

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening an issue or pull request. Report vulnerabilities according to [`SECURITY.md`](SECURITY.md); do not place secrets, personal data, or copyrighted exam banks in public issues.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
