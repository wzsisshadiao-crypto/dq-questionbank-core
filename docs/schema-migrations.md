# Schema Versions and Migrations

The canonical question document declares its `schema_version`. The library
reads and validates every released schema version and ships deterministic
migrations between them, so stored archives upgrade on your schedule instead
of a release day.

| Version | Status | Definition |
| --- | --- | --- |
| `1.0` | readable, writable (authoring default) | [`schema/question-set.schema.json`](../schema/question-set.schema.json) |
| `1.1` | readable, writable (current latest) | [`schema/question-set-1.1.schema.json`](../schema/question-set-1.1.schema.json) |

The constants `SUPPORTED_SCHEMA_VERSIONS` and `LATEST_SCHEMA_VERSION`
(package-level exports) state the same facts from code, and
`list_migrations()` reports the registered upgrade paths.

## What changed in 1.1

Schema 1.1 promotes the question-level analysis text from the free-form
`metadata.analysis` string to a first-class `analysis` field of content
blocks, next to `stem` and `solution`:

```json
{
  "schema_version": "1.1",
  "id": "q-1",
  "type": "short_answer",
  "language": "en",
  "stem": {"blocks": [{"type": "text", "text": "State the result."}]},
  "analysis": {"blocks": [{"type": "text", "text": "Factor before substituting."}]}
}
```

Rationale: the visual workspace already treats analysis as a first-class
search and editing scope, and mapping imports had to special-case it into
extension metadata. Promoting the field removes that inconsistency. The
`Question` model exposes it as `question.analysis` (`Content`), and semantic
validation checks its blocks exactly like `stem` and `solution`.

## Migrating stored documents

```python
from dq_questionbank import migrate, validate_with_schema

payload = json.loads(path.read_text(encoding="utf-8"))
upgraded = migrate(payload, "1.1")          # never mutates the input
issues = validate_with_schema(upgraded)     # [] when clean
path.write_text(json.dumps(upgraded, indent=2) + "\n", encoding="utf-8")
```

The built-in `1.0 -> 1.1` migration:

- bumps the set-level and per-question (including subquestion)
  `schema_version` to `1.1`;
- moves a non-empty string `metadata.analysis` to the `analysis` field as a
  text block;
- keeps every other extension metadata key untouched and drops `metadata`
  entirely when it becomes empty;
- leaves non-string `metadata.analysis` values in place (extension data is
  never reinterpreted);
- returns a deep copy, so the caller's payload is never mutated.

## Path selection and failure modes

`migrate()` refuses to guess. Given the registered edges it applies a direct
edge to the target when one exists; otherwise it takes the single forward hop
strictly below the target, and raises `SchemaVersionError` when:

- the payload has no `schema_version`, or a version is not numeric
  `major.minor`;
- no migration is registered from the current version (dead end);
- every registered target is at or beyond the requested version (the request
  would move the document sideways or backwards);
- more than one registered target leads toward the request (ambiguous fork);
- the walk revisits a version (circular registration).

`validate_with_schema` dispatches on the declared version and reports an
`unsupported_schema` issue for any version outside
`SUPPORTED_SCHEMA_VERSIONS` instead of validating against a guessed schema.
`load_schema(version)` and `schema_path(version)` accept the same versions
and raise for anything else.

## Fixtures and harnesses

- [`tests/fixtures/compatibility/migrations/1.0-to-1.1.json`](../tests/fixtures/compatibility/migrations/1.0-to-1.1.json)
  records the promoted-field example above as a source/expected pair
  (`dq-questionbank-migration-fixture-1`).
- `tests/test_schema_migration.py` pins the registration, the no-mutation
  guarantee, both rejection modes, and the model round trip.
- `tests/test_compatibility_fixtures.py` keeps the 0.9 -> 1.0 harness example
  demonstrating explicit `register_migration` for out-of-tree versions.

## Authoring note

New documents default to `1.0`; `1.1` is opt-in (set `schema_version`
explicitly or start from a migrated payload). Old readers that only know 1.0
will reject 1.1 documents loudly, which is the intended compatibility
signal — exchange `1.1` only with consumers that advertise it.
