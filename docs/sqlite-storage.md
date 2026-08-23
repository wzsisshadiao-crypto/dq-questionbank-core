# Reference SQLite Storage

`SqliteStorageAdapter` is a writable reference implementation of the
`StorageAdapter` protocol that uses only the Python standard-library
`sqlite3` module. It stores the canonical JSON payload of each question set
in one row of a `question_sets` table keyed by the question-set identifier.

## Usage

```python
from dq_questionbank import QuestionSet, SqliteStorageAdapter

with SqliteStorageAdapter("local-bank.sqlite3") as storage:
    storage.save(question_set)          # create or replace by id
    restored = storage.load(question_set.id)
```

A runnable demo builds a disposable database from the bundled synthetic
fixture and validates the round trip through the public validation API:

```bash
python examples/sqlite_storage_demo.py --db demo.sqlite3
```

## Behavior

- **Duplicate identifiers:** saving an id that already exists replaces the
  previous row entirely — last write wins, no history is kept. Each save is
  one transaction, so a partial write cannot be observed.
- **Determinism:** the canonical JSON serialization is deterministic
  (sorted keys, fixed separators), so repeated saves of the same payload
  produce identical stored content.
- **Fail-closed loads:** loading an identifier that was never saved raises
  `KeyError`; a payload that deserializes to a different identifier raises
  `ValueError`.
- **Identifiers:** the same restricted alphabet as the filesystem adapter
  (ASCII letters, digits, dots, hyphens, underscores).

## Trust boundary

The adapter opens only the database file you pass it. It never touches a
production database, performs no schema migrations, and keeps the core
database-neutral — this is a reference example, not the default backend.
Applications needing concurrency control, users, media, or migrations
should implement `StorageAdapter` in their own package. Generated database
artifacts are ignored by Git (`*.db`, `*.sqlite`, `*.sqlite3`).
