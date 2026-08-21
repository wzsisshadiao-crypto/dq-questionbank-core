# Changelog

All notable changes will be documented here. The project follows semantic versioning. `0.x` releases may introduce breaking changes.

## [0.7.0] - 2026-08-22

### Added

- Add one public review-first intake layer and `dq intake` CLI for preparing,
  reviewing, exporting, inspecting, and replaying import bundles.
- Ship five deterministic synthetic cases for manual browser entry, browser AI,
  regular AI Coding, PDF AI Coding, and exam-specific AI Coding with native OMML.
- Bind bundle files, evidence excerpts, AI proposals, candidates, and review
  decisions to SHA-256 digests; reject stale or out-of-scope transitions.
- Add a deterministic case generator plus real DOCX, PDF, and OMML fixtures.

### Changed

- Make canonical validation fail closed at CLI and local persistence boundaries,
  with a zero-install validator for the normative schema and explicit missing
  schema diagnostics.
- Reject unknown content-block and answer fields consistently in the JSON Schema
  and Python model instead of silently losing accepted data.
- Report incorrectly typed difficulty values as validation issues.

### Security

- Never persist intake candidates automatically; require an explicit decision for
  every candidate and omit rejected candidates from export.
- Extend the public-tree audit with exact binary fixture paths and signature checks.

## [0.6.0] - 2026-08-20

### Added

- Structured formula-block editing in the public Editor Center: an insert and
  edit dialog for inline `$...$` and display `$$...$$` math with the LaTeX
  source shown alongside its live KaTeX preview.
- Formula blocks in editor previews are now click-to-edit targets with
  keyboard activation, so an existing formula opens directly in the dialog.
- A dependency-free `formula.js` module that owns delimited-math parsing,
  insertion, replacement, and canonical flattening for the Editor Center.
- Focused JavaScript tests for insert, edit, boundary preservation, canonical
  round-trip, and the malformed-source recovery path, wired into the Python
  suite through an optional Node.js runner.

### Changed

- Display math now keeps its `$$` delimiters when canonical JSON is loaded
  into editor fields, so nearby text edits preserve block boundaries and the
  `metadata.display` flag survives the save round-trip.

### Boundary

- Private frontend code, private correction rules, and AI provider workflows
  remain outside the public repository.

## [0.5.0] - 2026-08-20

### Added

- Bilingual English and Simplified Chinese product site with deterministic
  GitHub Pages deployment, language-aware entry routing, and shared real
  workspace visuals.
- Chinese GitHub landing README featuring the mature Editor Center view for
  `DX_SX_154` while keeping the production database and private implementation
  outside the public repository.
- Structured choice editing in the public Editor Center, including stable
  option ids, add/remove controls, and single- or multiple-answer binding.
- Reviewable question metadata controls for grade, category, difficulty, tags,
  and source title/year.
- Formula-preserving editor input parsing and explicit saved/unsaved/saving
  state handling with a pending-edit navigation guard.

### Changed

- Keep English normative for APIs, schemas, CLI, technical documentation, and
  contribution contracts while allowing maintained localized product and
  quick-start pages.

### Boundary

- Image-pool editing, interactive table authoring, and private correction
  providers remain outside this release. The public editor uses canonical
  content blocks and deterministic local checks.

## [0.4.0] - 2026-08-17

### Added

- Operational Paper Center for selecting, ordering, and exporting an active
  collection as canonical Question Set JSON.
- Import Center, Bank Data coverage dashboard, and deterministic Quality Center
  with direct Editor Center handoff.
- Ten-question synthetic mathematics case spanning multiple subjects, source
  years, question types, formulas, choices, and a structured Cayley table.

### Changed

- Expand the public frontend from a Question Bank and editor demonstration into
  a connected local workflow while retaining explicit boundaries around AI,
  image repair, candidate review, persisted quality history, and Word macros.
- Rebuild the public Editor Center as a dark, dense workbench with question
  context, horizontal field navigation, rendered-first content, source toggles,
  live math previews, save state, and a deterministic quality side panel.
- Add public source-year support to the reviewed SQLite case adapter.

- Reorder the README around a real visual-workspace screenshot, immediate local
  quick start, current capabilities, and clear user/technical documentation
  paths.
- Clarify that contributors do not need access to the private application and
  replace the stale release-gate reference with the checks actually required.
- Organize the roadmap around foundation, visual workspace, import/review,
  daily question work, Word publishing, and 1.0 readiness.
- Add a repository social-preview asset based on the real public workspace and
  route new issues through explicit workstream and public-data questions.

### Fixed

- Render explicitly delimited LaTeX safely across question text, table cells,
  answers, and solutions, with readable fallback when a formula is invalid.
- Mark every mathematical expression in the bundled group-theory case so the
  public screenshot and workspace no longer expose raw `p^2`-style source.

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
