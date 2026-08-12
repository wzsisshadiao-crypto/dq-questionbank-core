# Compatibility Policy

## Package versions

The package follows semantic versioning:

- `MAJOR`: incompatible stable API changes
- `MINOR`: backward-compatible features; during `0.x`, may include documented breaking changes
- `PATCH`: backward-compatible fixes

## Schema versions

Schema versions use `MAJOR.MINOR`. Unsupported versions produce validation errors. Readers do not guess migrations.

## Round-trip guarantees

- JSON: canonical object equality after serialize and deserialize
- Generated Markdown: canonical object equality through embedded markers
- Generated LaTeX: canonical object equality through comment markers
- DOCX: documented core-field equivalence; visual formatting and nested composite layout are best effort
- Arbitrary Markdown, LaTeX, and DOCX: best-effort import only for documented constructs

## Python support

The initial matrix is Python 3.10, 3.11, and 3.12. Dropping a supported Python version requires a minor release during `0.x` and a major release after `1.0`.

