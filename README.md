# DQ QuestionBank Core

Open infrastructure for structured educational questions.

DQ QuestionBank Core is a database-neutral Python library, command-line tool, and local browser playground for importing, validating, converting, and exchanging educational questions. Its versioned canonical model supports multilingual text, LaTeX math, images, tables, answer types, source provenance, taxonomy references, and composite questions.

This repository is an independent open-core extraction. It contains no production question bank, user data, private database, commercial workflow, or built-in AI provider.

> Status: `0.1.0` alpha. The canonical JSON model is usable, but compatibility guarantees remain pre-1.0.

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
- English-language CLI and local browser playground
- No database, frontend framework, or AI provider lock-in

## Installation

From a clone:

```bash
python -m venv .venv
python -m pip install -e ".[docx]"
```

For development:

```bash
python -m pip install -e ".[docx,dev]"
```

Python 3.10, 3.11, and 3.12 are the initial supported versions.

## Quick start

Validate the synthetic sample:

```bash
dq validate examples/sample_questions.json
```

Convert canonical JSON to Markdown or LaTeX:

```bash
dq convert examples/sample_questions.json --to markdown -o questions.md
dq convert examples/sample_questions.json --to latex -o questions.tex
```

Import a DOCX document:

```bash
dq import exam.docx -o questions.json --assets-dir imported_assets
```

Launch the local, English-language playground:

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
- `validation.py`: structural and safety rules
- `interfaces.py`: extension contracts
- `registry.py`: built-in format discovery
- `formats/`: JSON, Markdown, LaTeX, and DOCX adapters
- `cli.py`: thin command wrapper over the library
- `web/`: static local playground; no server-side data storage

The architecture proposal and private/public boundary are documented in [`docs/oss-architecture-proposal.md`](docs/oss-architecture-proposal.md) and [`OPEN_SOURCE_BOUNDARY.md`](OPEN_SOURCE_BOUNDARY.md).

## Development

```bash
python -m unittest discover -s tests -v
python -m ruff check src tests scripts
python -m build
python scripts/audit_public_tree.py
python scripts/check_docs.py
```

The test suite covers model serialization, schema conformance, validation, unsafe asset paths,
CLI behavior, format round trips, DOCX conversion, composite questions, formulas, documentation
links, and the English-only public interface.

## Roadmap

- Stabilize the `1.x` compatibility policy through real external integrations
- Add richer DOCX style profiles and table/image placement fidelity
- Add parser conformance fixtures contributed under explicit licenses
- Add optional IMS QTI adapters
- Publish extension entry-point discovery after the plugin API matures

See [`docs/roadmap.md`](docs/roadmap.md) for release milestones.

## Contributing and security

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening an issue or pull request. Report vulnerabilities according to [`SECURITY.md`](SECURITY.md); do not place secrets, personal data, or copyrighted exam banks in public issues.

## License

A final license has not been selected. This is a release blocker, not an invitation to use the code without permission. See [`LICENSE_RECOMMENDATION.md`](LICENSE_RECOMMENDATION.md). A valid OSI-approved `LICENSE` file must be added before the repository is announced as open source.
