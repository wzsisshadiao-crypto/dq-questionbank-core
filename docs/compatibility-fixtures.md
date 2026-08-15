# Compatibility Fixtures

The executable compatibility fixtures live under
`tests/fixtures/compatibility/`. They are intentionally small, original, and
English-language synthetic data.

- `schema-1.0/question-set.json` is a canonical schema 1.0 round-trip fixture.
- `migrations/0.9-to-1.0.json` defines an input and expected output for the
  migration-framework harness.

The migration fixture demonstrates that callers must register an explicit
migration before `migrate()` changes a payload. It does **not** declare schema
0.9 supported and does not install a migration into the package. Unsupported
schema versions continue to fail closed unless an application registers its own
migration path.

The fixture suite is an initial 1.0-roadmap deliverable, not a declaration that
the package itself has reached version 1.0. Future schema versions must add
their own synthetic input, expected output, migration guidance, and compatibility
tests before changing the normative schema.
