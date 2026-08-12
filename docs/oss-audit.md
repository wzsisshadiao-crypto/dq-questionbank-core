# Private Repository OSS Audit

Audit date: 2026-08-12  
Scope: read-only inspection of the local private question-bank project  
Method: architecture inventory, targeted source inspection, file classification, credential-pattern scan, and test inventory. No private data was copied.

## 1. Current architecture

The private product is a Windows-oriented Python application with a Flask backend, a large static JavaScript frontend, SQLite storage, DOCX import/export, image storage, quality-review workflows, backup/recovery tools, and optional AI-assisted repair.

The main request path is:

```text
Static browser UI
      |
      v
Large Flask application
      |---- SQLite question/paper schema
      |---- upload and image-relation storage
      |---- DOCX parser and Word exporter
      |---- review and quality subsystems
      |---- optional AI repair/import pipeline
```

The backend route file and primary frontend script are both containment monoliths. Existing architecture tests explicitly cap their line counts rather than treating them as modular components. Storage paths and product workflows are referenced directly from request handlers.

## 2. Technology stack

- Python with Flask and Flask-CORS
- SQLite
- Static HTML, CSS, and JavaScript
- `python-docx`, `lxml`, `latex2mathml`, and `officemath2latex`
- Pillow for image handling
- Optional OpenAI-compatible and vision-provider clients
- PDF utilities and fuzzy matching
- Windows batch launch and maintenance scripts

## 3. Entry points

- Windows start/stop scripts launch the Flask application.
- The Flask application serves the UI and a broad REST API.
- Separate scripts handle transfer packaging and Word integration.
- AI-assisted import also has a command-oriented entry point.

## 4. Data model and database

The private schema is relational and product-oriented. It contains question, choice, paper, paper-question, image, table, review, quality, recycle, and migration concepts. Question fields are coupled to the current UI, bilingual conventions, subject categories, verification state, paper ordering, and local image paths.

This schema should not become the public interchange contract. The OSS model therefore uses nested JSON objects and explicit adapters.

## 5. Import and export flow

- DOCX parsing contains valuable general techniques but is mixed with source-specific shading, numbering, language, answer-section, image, and math heuristics.
- Word export is capable but tightly connected to the private SQLite schema and product layout preferences.
- AI import and repair directly understand private question fields and persistence behavior.

The first public release uses a smaller, documented convention-based DOCX adapter. More sophisticated algorithms may move later only through narrow extraction and synthetic regression tests.

## 6. Coupling points

- Request handlers open the production SQLite database directly.
- Export code queries private tables instead of receiving canonical models.
- Import code combines parsing, repair, validation, ID allocation, image staging, and persistence.
- Frontend behavior assumes private route names and response shapes.
- AI configuration and provider behavior are present inside the private backend.
- Windows filesystem layout is part of runtime behavior.

## 7. Open-source candidates

- A versioned canonical Question Schema
- Database-neutral models and validation
- Importer/exporter protocols
- Safe asset-reference rules
- Generic JSON, Markdown, LaTeX, and convention-based DOCX adapters
- A thin CLI and local schema playground
- Synthetic conformance fixtures

## 8. Private-only components

- Production data and media
- Product UI and business workflows
- Direct database schema and migrations
- AI prompts, provider configuration, and repair pipeline
- Backup, recovery, review, and quality operations
- Maintenance history, scrapers, and one-off scripts

## 9. Sensitive information risks

The private tree contains a non-example AI configuration file with live-looking provider credentials. Those credentials were not copied. They must be revoked and rotated before any source derived from the private tree is made public.

The private tree also contains approximately:

- 9,751 uploaded files (about 760 MiB)
- 55 database backup files (about 854 MiB)
- 9 log files (about 7.7 MiB)
- multiple SQLite database files, temporary outputs, generated previews, and historical maintenance artifacts

These categories are categorically excluded from the public repository.

Deleting a file from a working tree does not remove it from Git history. If the private project is ever initialized or pushed independently, its entire history must be scanned before publication.

## 10. Copyright and privacy risks

The databases, uploaded images, generated previews, and parser regression artifacts may contain real exam or publisher material. Their provenance was not established during this audit. None are suitable for public fixtures. The OSS examples were written from scratch and contain no real user, school, student, or exam data.

## 11. Test and documentation state

The private project has a substantial regression suite, especially around math cleanup, DOCX behavior, frontend rules, image handling, backup safety, and quality workflows. Many tests encode product-specific assumptions and cannot be copied wholesale. Documentation is mostly operational and private-product focused.

## 12. Largest technical debts affecting extraction

1. Backend and frontend containment monoliths
2. Parser, validator, repair, persistence, and provider concerns mixed together
3. Database-shaped interchange objects
4. Product-specific file paths and Windows assumptions
5. Historical encoding corruption in comments and documents
6. Large stores of unclassified real content and backups
7. Credentials stored in a local JSON configuration file

## Audit conclusion

An allowlist-based clean extraction is safer than repository copying. The public repository created from this audit contains newly organized general-purpose code and synthetic data only. The private project remains the upstream product, connected later through private adapters.

