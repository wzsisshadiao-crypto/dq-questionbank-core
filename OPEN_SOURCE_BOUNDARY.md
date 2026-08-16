# Open-Source Boundary

This boundary protects the private product while allowing the public core to evolve independently.

## Public by design

- Canonical question and question-set models
- JSON Schema and compatibility rules
- Structural validation and safe asset-reference checks
- Importer/exporter protocols and format registry
- Generic JSON, Markdown, LaTeX, and DOCX adapters
- CLI and local browser playground
- Local-first visual workspace and reviewed SQLite case adapter
- Auditable synthetic database case generated from original fixture data
- Synthetic examples, tests, documentation, and CI
- Generic visual workflows rebuilt against the canonical model and synthetic data
- Generic review, editor, quality, paper-assembly, and Word publishing contracts

These components have independent value, require no production database, and can be used by third parties without knowledge of the private application.

## Eligible only after targeted review

- Generic math normalization algorithms
- Generic OMML-to-LaTeX conversion helpers
- Generic DOCX layout heuristics
- Generic image-placement utilities
- Generic process-based import orchestration and source-evidence records
- Generic candidate review and paper-assembly behavior
- Generic editor and quality-inspection behavior
- Loopback-only Word macro helpers and refreshable reference blocks

The private implementation currently mixes some of these capabilities with
product-specific assumptions, language-specific cleanup rules, local paths,
database fields, private source material, and historical patches. Any future
contribution must be extracted by a narrow, reviewed change with synthetic
tests. Copying an entire private module is prohibited.

## Private-only

- Production SQLite databases and database backups
- Uploaded question images and orphan-image archives
- Unreviewed real questions, papers, answers, solutions, sources, and customer content
- Logs, request traces, cleanup state, and local runtime artifacts
- AI configuration, credentials, private prompts, learned correction history, and provider wiring
- Production backup, recovery, authorization, billing, and deployment workflows
- Internal account, authorization, pricing, and operational code
- One-off scraping, migration, forensic, and maintenance scripts
- Private production frontend behavior and product-specific interaction design

The last item does not make the product category private. Generic workflow and
interaction behavior may be independently implemented in the public application;
production-specific code, assumptions, and private data must not be copied.

## Dependency direction

The private product and public local application may depend on `dq_questionbank`. The public packages must never import the private product.

```text
Private application --> private adapters --> DQ QuestionBank Core
                                           ^
Third-party apps ----> third-party adapters-|
Public local app ----> reviewed case adapter-|
```

## Data policy

Only synthetic, original, public-domain, or clearly licensed fixtures may enter `examples/` or `tests/`. Source license and attribution belong in `SourceMetadata` when applicable. A non-synthetic public case must be built as a new allowlisted artifact after a separate content, privacy, copyright, and SQLite stale-page review. No production row, image, document, log excerpt, or database dump may be used directly as a fixture.

## Release gate

Every proposed release must pass `python scripts/audit_public_tree.py`, all tests, a manual diff review, a credential scan, a copyright/provenance review, and the checklist in `OSS_READINESS_REPORT.md`.

