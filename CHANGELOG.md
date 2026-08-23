# Changelog

All notable changes will be documented here. The project follows semantic versioning. `0.x` releases may introduce breaking changes.

## [Unreleased]

### Added

- Safer schema migration support between question model versions (#1):
  schema 1.1 promotes question-level `metadata.analysis` to a first-class
  `analysis` content-block field, shipped as
  `schema/question-set-1.1.schema.json` next to the unchanged 1.0 schema.
  `load_schema`/`schema_path` take an optional version, the `Question`
  model round-trips `analysis`, and `validate_with_schema` dispatches on
  the declared version while rejecting unknown ones explicitly. The
  framework's first built-in `migrate(payload, "1.1")` edge bumps versions,
  preserves unrelated extension metadata, never mutates its input, and
  refuses ambiguous or backward paths with `SchemaVersionError`. New
  constants `SUPPORTED_SCHEMA_VERSIONS` and `LATEST_SCHEMA_VERSION`; guide
  in `docs/schema-migrations.md`; source/expected fixture and path-selection
  tests included.

## [0.15.0] - 2026-08-23

### Added

- OMML-to-LaTeX import adapter (`dq_questionbank.omml_import`): reads
  native Word math (`m:oMath`/`m:oMathPara`) from a DOCX with the
  standard library only, maps fractions, scripts, roots, delimiters,
  named functions, and n-ary operators to deterministic LaTeX, and
  preserves unknown constructs as text with an unsupported report
  instead of guessing (#56).
- Asset-evidence contract for image repair
  (`dq_questionbank.asset_repair`): `AssetRepairProposal` binds the
  question block, asset reference, current digest, and replacement
  digest; binding enforces safe-relative-path rules, previewing
  re-verifies both digests, and there is deliberately no
  accept-and-write step in the core (#57).
- Formula-image transcription candidates
  (`dq_questionbank.formula_images`): digest-bound review records for
  rasterized formulas with human transcription, contributor provenance,
  and fail-closed evidence checks; no OCR engine or network access (#59).
- Safe backup-and-restore drill (`examples/backup_restore_drill.py`):
  backup, verify, restore, and compare phases over a caller-chosen
  workspace with SHA-256 manifests, fail-closed verification, and a
  written guide linked from the docs index (#60).

## [0.14.0] - 2026-08-23

### Added

- Soft-delete Recycle Bin in the local visual workspace: recycling a
  question keeps it in the canonical payload (exports keep it until
  permanent delete), restoring returns it to its original position, and
  permanent delete removes it for real while clearing derived selections
  and marking the workspace unsaved (#58).
- Safe plugin-discovery example (`examples/plugin_discovery_demo.py`):
  listing installed entry points never loads plugin code, and the explicit
  opt-in flag is the only step that executes third-party registrars; the
  documentation pins the deterministic clean-environment output (#38).
- Blank-cell table fixture package: an original synthetic table with one
  intentionally empty cell, covered by a DOM-level rendering check
  (empty-but-present cell, shape preserved) and a canonical round-trip
  test (#37).

## [0.13.0] - 2026-08-23

### Added

- Review Center rows are keyboard-friendly: each row is focusable with a
  descriptive aria-label, Enter or Space activates the mark-reviewed/undo
  action, child-button activation stays native (no double firing), and a
  visible focus outline works in both themes (#16).
- Table-and-math rendering regression fixture with focused DOM-level tests:
  the real `app.js` runs in a Node `vm` context with a scripted KaTeX
  double, proving table rows and header cells survive, math blocks and
  table-cell formulas render through KaTeX, and a rendering failure keeps
  the source visible while removing nothing (#27).
- Source-year filter regression test covering the served control, the exact
  matching predicate, and the bundled case's 2025 subset plus the
  unknown-year empty state (#9).

## [0.12.0] - 2026-08-23

### Added

- Public reviewable import-candidate-session contract
  (`dq_questionbank.review_session`): `ImportCandidateSession` and
  `ImportCandidate` wrap the canonical digest-bound session documents in
  stable dataclasses without changing the wire format.
- Sessions now retain the parser identity next to source evidence.
- Deterministic candidate revisions: every candidate starts at revision 1,
  and a reviewed edit bumps the revision while rebinding the question
  digest; plain accepts/rejects leave it unchanged.
- Stable serialized fixtures for pending, reviewed (accepted with edit),
  rejected, and exported states, plus contract documentation and
  source-specific profile extension guidance in `docs/review-sessions.md`.

### Security

- No candidate state implies persistence or AI approval; export still
  requires an explicit decision for every candidate and never writes to a
  store.

## [0.11.0] - 2026-08-23

### Added

- Writable reference SQLite storage adapter (`dq_questionbank.sqlite_storage`)
  implementing the public `StorageAdapter` save/load contract with only the
  standard-library `sqlite3` module.
- Deterministic canonical-JSON persistence per question-set identifier;
  saving an existing identifier replaces the row in one transaction
  (documented last-write-wins behavior).
- `contains` and `stored_ids` helpers for deterministic state inspection.
- Runnable demo `examples/sqlite_storage_demo.py` that builds a disposable
  database from the bundled synthetic fixture and validates the round trip
  through the public validation API.
- Storage documentation in `docs/sqlite-storage.md` covering the workflow,
  duplicate-id behavior, and the trust boundary.

## [0.10.0] - 2026-08-23

### Added

- Public revision-bound quality-finding contract (`dq_questionbank.quality_findings`):
  a finding binds a question id, an exact target field path, a rule id, the
  ruleset version, and deterministic SHA-256 fingerprints over every field
  the rule read.
- `detect_quality_findings` runs the deterministic LaTeX rules over math
  blocks in stems, solutions, and choices; repairable sources carry
  preview-only repair data.
- `judge_finding` records human accept/reject decisions as a separate
  operation that fails closed with `StaleFindingError` on stale content.
- Cross-field findings go stale when any declared input dependency changes;
  unrelated edits do not invalidate a finding.
- Stable serialized fixtures for current, stale, accepted, and rejected
  findings, plus the contract documentation in `docs/quality-findings.md`.

## [0.9.0] - 2026-08-23

### Added

- Deterministic LaTeX repair rule set: bare function names (`sin x` ->
  `\sin x`), `\left(`/`\right)` inner spacing normalization, and doubled
  operator-spacing collapse outside `\text{...}` prose, each with a stable
  rule ID and a visible before/after preview on the outcome.
- `repair_latex_source` composes the safe rules (plus the existing
  missing-closing-brace repair) in a fixed order and reports every applied
  rule ID on `applied_rules`.
- Synthetic before/after rule-set fixture covering composition, preserved
  prose spacing, and the fail-closed ambiguous case.

### Security

- Mismatched plain delimiters such as `(x+1]` are never rewritten; they are
  reported as a `latex-mismatched-delimiters` manual-review finding with the
  source left untouched.

## [0.8.0] - 2026-08-22

### Added

- Ship the complete provider-neutral Word publishing path: managed `w:sdt`
  DOCX export, canonical question fingerprints, envelope validation, ordered
  refresh, stale detection, and single-block rollback.
- Add a loopback-only, credential-free JSON bridge for inserting and refreshing
  reviewed canonical questions without database or remote-service access.
- Bundle an auditable Word VBA template with insert, refresh-current,
  refresh-all, compose-border, and final-render commands.
- Add `dq word-publish`, `dq word-serve`, and `dq word-macro` so the workflow can
  be adopted without application-specific glue code.
- Cover Open XML markers, deterministic managed document XML, bridge safety,
  compose/final output, stale retention, and VBA safety properties in tests.

### Security

- Reject non-loopback origins, credentials, duplicate block ids, unknown
  envelope versions, and unsupported refresh or rollback policies.
- Never execute document content or persist candidates through the Word bridge;
  stale and failed blocks keep their prior content.

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
