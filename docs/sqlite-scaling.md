# SQLite Scaling Notes

Practical recipes for keeping a local SQLite question bank responsive as the
row count grows; they track
[#100](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues/100).
Every measurable claim is reproducible with
[`scripts/bench_sqlite_scaling.py`](../scripts/bench_sqlite_scaling.py), a
dependency-free benchmark over synthetic rows.

## Scope: what the reference adapter actually stores

[`SqliteStorageAdapter`](sqlite-storage.md) stores the canonical JSON payload
of each question set in **one row** of `question_sets`:

```sql
CREATE TABLE IF NOT EXISTS question_sets (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    question_count INTEGER NOT NULL
)
```

There are no per-question rows, no full-text index, and no index beyond the
implicit primary-key index on `id`; the adapter also never performs schema
migrations. Recipes below that name `question_rows`, `question_rows_archive`,
or `question_rows_fts` therefore target a **derived projection** that a
downstream bank maintains beside the canonical payloads: re-parse each saved
set and upsert its projected rows in the same transaction. Recipes that use
only `question_sets` columns work against the reference schema today. The
benchmark script likewise builds its own synthetic projection in memory and
never opens a real bank.

## 1. Composite indexes for ordered scans

List views filter on one column and sort on others. A composite index ordered
filter-first, sort-second lets SQLite read matching rows already in result
order - no full scan of the table, no temporary b-tree sort. Verify with
`EXPLAIN QUERY PLAN`: the plan should read `SEARCH ... USING INDEX` and must
not contain `USE TEMP B-TREE FOR ORDER BY`.

```sql
CREATE INDEX idx_rows_set_created
    ON question_rows (set_id, created_at, ordinal);

EXPLAIN QUERY PLAN
SELECT payload FROM question_rows
WHERE set_id = ?
ORDER BY created_at, ordinal;
```

On the reference table itself, the primary-key index on `id` already serves
ordered scans: `stored_ids()` runs `SELECT id FROM question_sets ORDER BY id`
directly against it.

## 2. Two-phase list queries: count, then page

Never load every payload and slice pages in application code. Let SQLite
count the rows first, then fetch exactly one page; both statements use the
same composite index, and the page read touches only the rows it returns.

```sql
SELECT COUNT(*) FROM question_rows WHERE set_id = ?;

SELECT payload FROM question_rows
WHERE set_id = ?
ORDER BY created_at, ordinal
LIMIT ? OFFSET ?;
```

The same pattern works against the reference schema today, paging over sets
without reading a single payload - `question_count` is a real column, so set
totals need no JSON parsing:

```sql
SELECT id, question_count FROM question_sets
ORDER BY id LIMIT ? OFFSET ?;
```

For very deep pages, prefer keyset paging (`WHERE (created_at, ordinal) > (?, ?)`)
over ever-growing offsets.

## 3. Hot/cold table split

Retired years are written once and read rarely, yet they inflate every scan of
the active table. Keep them in a twin archive table with the same shape, move
rows past a cutoff inside one transaction, and query the union only when the
interface really needs history.

```sql
BEGIN;
INSERT INTO question_rows_archive
    (set_id, ordinal, stem, difficulty, created_at, payload)
SELECT set_id, ordinal, stem, difficulty, created_at, payload
FROM question_rows WHERE created_at < :cutoff;
DELETE FROM question_rows WHERE created_at < :cutoff;
COMMIT;
```

Because the reference adapter replaces a whole set on every save (last write
wins), a downstream projection must re-project that set's rows after each
save - including rows previously moved to the archive - or the split drifts
out of sync.

## 4. FTS MATCH and keeping the index in sync

Stem search over thousands of JSON payloads means a full scan per query. An
FTS5 virtual table inverts the text once, and `MATCH` queries that index:

```sql
CREATE VIRTUAL TABLE question_rows_fts USING fts5(
    stem,
    content='question_rows',
    content_rowid='rowid'
);
INSERT INTO question_rows_fts (rowid, stem)
SELECT rowid, stem FROM question_rows;

CREATE TRIGGER rows_ai AFTER INSERT ON question_rows BEGIN
    INSERT INTO question_rows_fts (rowid, stem) VALUES (new.rowid, new.stem);
END;
-- Mirror triggers for UPDATE and DELETE keep the index aligned; an
-- external-content delete looks like:
-- INSERT INTO question_rows_fts (question_rows_fts, rowid, stem)
--     VALUES ('delete', old.rowid, old.stem);
```

Sync from one writer path only - the projection's triggers - so re-imports
cannot skip the index. FTS5 is compile-time optional; check your build with
`SELECT sqlite_compileoption_used('ENABLE_FTS5');` before relying on it.

## 5. ATTACH-based read-only archives

An archive can also live in a separate database file, attached only for the
rare queries that need it. Opening it with `mode=ro` guarantees a reader can
never mutate history, and `DETACH` releases it before the connection closes.

```python
import sqlite3

connection = sqlite3.connect("bank.sqlite3", uri=True)
connection.execute(
    "ATTACH DATABASE ? AS archive", ("file:archive-2023.sqlite3?mode=ro",)
)
rows = connection.execute(
    "SELECT set_id, ordinal FROM question_rows "
    "UNION ALL SELECT set_id, ordinal FROM archive.question_rows_archive"
).fetchall()
connection.execute("DETACH archive")
```

Treat archived files like any other bank data: produce them through the
verified backup drill in [`docs/backup-restore.md`](backup-restore.md), never
by copying a live database mid-transaction.

## 6. Maintenance cadence

SQLite needs occasional housekeeping; tie each task to an event rather than a
calendar so nothing heavyweight runs during interactive editing.

| When | Run | Why |
| --- | --- | --- |
| after a bulk import or archive move | `ANALYZE;` | refresh planner statistics |
| at the end of an ordinary session | `PRAGMA optimize;` | cheap incremental statistics |
| before every verified backup | `PRAGMA integrity_check;` | catch corruption early |
| after deleting many rows, offline only | `VACUUM;` | reclaim space; rewrites the file |

## Reproduce the numbers

```bash
python scripts/bench_sqlite_scaling.py
```

The benchmark builds a synthetic projection in memory, measures each scenario
`--repeats` times, and prints medians next to the query plans, so the recipes
above can be re-verified after any schema change.
