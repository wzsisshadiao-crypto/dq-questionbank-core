# Changelog

All notable changes will be documented here. The project follows semantic versioning while recognizing that `0.x` releases may introduce breaking changes.

## [Unreleased]

## [0.2.0] - 2026-08-12

### Added
- Custom exception hierarchy: `QuestionBankError`, `FormatError`, `FormatDetectionError`, `FormatLoadError`, `FormatWriteError`, `SchemaError`, `SchemaNotFoundError`, `SchemaValidationError`, `SchemaVersionError`.
- Protocol enforcement in `FormatRegistry`: `register_importer` and `register_exporter` reject non-conforming objects.
- Unified validation pipeline: `validate_with_schema()` runs JSON Schema then semantic rules in one pass.
- Schema version migration framework: `register_migration()`, `migrate()`, `list_migrations()`.
- Lazy format module loading: LaTeX and DOCX modules are only imported when available.
- Thread-safe `FormatRegistry` using `threading.Lock`.
- Web playground smoke tests: HTML structure, CSS rules, and JS syntax.

### Changed
- `registry.py` raises `FormatDetectionError` instead of `ValueError`.
- `schema.py` raises `SchemaNotFoundError` instead of `FileNotFoundError`.
- CLI catches domain-specific exceptions for clearer error messages.

## [0.1.0] - 2026-08-12

### Added

- Canonical Question Schema version 1.0.
- JSON, Markdown, LaTeX, and DOCX import/export adapters.
- Validation for choices, composite questions, assets, paths, languages, and schema versions.
- Extension protocols for importers, exporters, storage, and AI providers.
- English-language CLI and local browser playground.
- Synthetic examples, tests, documentation, CI, and public-tree audit tooling.

