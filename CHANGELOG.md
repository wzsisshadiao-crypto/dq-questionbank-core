# Changelog

All notable changes will be documented here. The project follows semantic versioning. `0.x` releases may introduce breaking changes.

## [Unreleased]

## [0.2.1] - 2026-08-12

### Fixed

- Remove spurious `version` keys from `[tool.ruff.lint]` in `pyproject.toml`.
- Unify version string to a single source in `dq_questionbank.__init__.__version__`.
- `dq --version` now reads the package version instead of using a duplicate hard-coded constant.
- Add `License :: OSI Approved :: Apache Software License` classifier.
- Remove duplicate `__version__` assignments left over from earlier fast-iteration rounds.

### Changed

- CLI exception imports are now at module level (not buried at the bottom of the file).

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

- Initial open-source release with canonical question schema, four format adapters, CLI, and browser playground.
