# Changelog

All notable changes will be documented here. The project follows semantic versioning. `0.x` releases may introduce breaking changes.

## [Unreleased]

### Changed

- Reorder the README around a real visual-workspace screenshot, immediate local
  quick start, current capabilities, and clear user/technical documentation
  paths.
- Clarify that contributors do not need access to the private application and
  replace the stale release-gate reference with the checks actually required.
- Organize the roadmap around foundation, visual workspace, import/review,
  daily question work, Word publishing, and 1.0 readiness.
- Add a repository social-preview asset based on the real public workspace and
  route new issues through explicit workstream and public-data questions.

## [0.3.0] - 2026-08-17

### Added

- Opt-in, deterministic discovery for third-party format plugins through the
  `dq_questionbank.plugins` entry-point group.
- Repository-owned Wiki source, manifest, and export/sync/check utility.
- English public-interface policy for maintained documentation and community
  contributions.
- Stable public API manifest and CI compatibility check.
- Executable synthetic schema and migration-framework compatibility fixtures.
- Reference `FilesystemStorageAdapter` with deterministic paths, atomic writes,
  and path-traversal rejection.
- Local-first visual question-bank workspace with canonical JSON import, local
  persistence, search and filters, structured question cards, in-card answer
  review, editing, and JSON export.
- Reviewed synthetic SQLite database case with an English group-theory question,
  KaTeX formulas, and a responsive 9-by-9 Cayley table.

### Changed

- Align the public Question Bank and Editor Center layouts with the mature
  private application's navigation, filters, question cards, and collection
  directory while keeping private APIs and operational data out of the public
  repository.
- Select database-case stems, choices, answers, solutions, and sources using the
  case language; the bundled case now renders English-only question content.

### Security

- Keep the local workspace bound to loopback and reject cross-origin writes.
- Audit the public tree in CI and open reviewed SQLite cases read-only with
  immutable and query-only SQLite settings.

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
