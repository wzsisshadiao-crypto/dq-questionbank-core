# Open-Source Boundary

This boundary protects the private product while allowing the public core to evolve independently.

## Public by design

- Canonical question and question-set models
- JSON Schema and compatibility rules
- Structural validation and safe asset-reference checks
- Importer/exporter protocols and format registry
- Generic JSON, Markdown, LaTeX, and DOCX adapters
- CLI and local browser playground
- Synthetic examples, tests, documentation, and CI

These components have independent value, require no production database, and can be used by third parties without knowledge of the private application.

## Eligible only after targeted review

- Generic math normalization algorithms
- Generic OMML-to-LaTeX conversion helpers
- Generic DOCX layout heuristics
- Generic image-placement utilities

The private implementation currently mixes some of these capabilities with product-specific assumptions, language-specific cleanup rules, local paths, database fields, and historical patches. Any future contribution must be extracted by a narrow, reviewed change with synthetic tests. Copying an entire private module is prohibited.

## Private-only

- Production SQLite databases and database backups
- Uploaded question images and orphan-image archives
- Real questions, papers, answers, solutions, sources, and customer content
- Logs, request traces, cleanup state, and local runtime artifacts
- AI configuration, credentials, prompts, repair pipeline, and provider wiring
- Commercial review, quality-center, backup, recovery, and deployment workflows
- Internal account, authorization, pricing, and operational code
- One-off scraping, migration, forensic, and maintenance scripts
- Private frontend behavior and product-specific interaction design

## Dependency direction

The private product may depend on `dq_questionbank`. The public core must never import the private product.

```text
Private application --> private adapters --> DQ QuestionBank Core
                                           ^
Third-party apps ----> third-party adapters-|
```

## Data policy

Only synthetic, original, public-domain, or clearly licensed fixtures may enter `examples/` or `tests/`. Source license and attribution belong in `SourceMetadata` when applicable. No production row, image, document, log excerpt, or database dump may be used as a fixture.

## Release gate

Every proposed release must pass `python scripts/audit_public_tree.py`, all tests, a manual diff review, a credential scan, a copyright/provenance review, and the checklist in `OSS_READINESS_REPORT.md`.

