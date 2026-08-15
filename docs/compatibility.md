# Compatibility Policy

## Package versions

The package follows semantic versioning:

- `MAJOR`: incompatible stable API changes
- `MINOR`: backward-compatible features; during `0.x`, may include documented breaking changes
- `PATCH`: backward-compatible fixes

## Schema versions

Schema versions use `MAJOR.MINOR`. Unsupported versions produce validation errors. Readers do not guess migrations.

The current schema version is `1.0`; it is separate from the package release
version. The package has not declared a 1.0 release. See
[Compatibility Fixtures](compatibility-fixtures.md) for the executable current
schema and migration-framework checks.

## Stable Python API

The package-level public API is recorded in
[`public-api-manifest.json`](public-api-manifest.json). CI rejects removed,
renamed, or signature-incompatible exports and documented members. See
[Stable Public Python API](public-api.md) for the update procedure.

## Round-trip guarantees

- JSON: canonical object equality after serialize and deserialize
- Generated Markdown: canonical object equality through embedded markers
- Generated LaTeX: canonical object equality through comment markers
- DOCX: documented core-field equivalence; visual formatting and nested composite layout are best effort
- Arbitrary Markdown, LaTeX, and DOCX: best-effort import only for documented constructs

## Python support

The initial matrix is Python 3.10, 3.11, and 3.12. Dropping a supported Python version requires a minor release during `0.x` and a major release after `1.0`.

