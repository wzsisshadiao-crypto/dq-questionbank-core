"""Benchmark the SQLite scaling recipes documented in docs/sqlite-scaling.md.

Builds a synthetic per-question projection in an in-memory database (no real
bank file is ever opened) and measures two scenarios from that guide: (1) an
ordered scan of one set's rows - naive full scan plus sort versus a composite
index on (set_id, created_at, ordinal); (2) a page fetch - full read plus
Python slice versus a two-phase COUNT-then-page query.

Rows come from arithmetic sequences only (no unseeded randomness); every
measurement is the median of ``--repeats`` runs, and query plans print next
to the timings. Labels, row counts, and plans are deterministic; timings
vary by machine. Exits 0.

    python scripts/bench_sqlite_scaling.py --sets 40 --rows-per-set 500
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import time

DIFFICULTIES = ("easy", "medium", "hard")

PROJECTION_SCHEMA = (
    "CREATE TABLE question_rows ("
    "set_id TEXT NOT NULL, ordinal INTEGER NOT NULL, stem TEXT NOT NULL, "
    "difficulty TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
)

ORDERED_SCAN_SQL = (
    "SELECT payload FROM question_rows "
    "WHERE set_id = ? ORDER BY created_at, ordinal"
)
COUNT_SQL = "SELECT COUNT(*) FROM question_rows WHERE set_id = ?"
PAGE_SQL = (
    "SELECT payload FROM question_rows WHERE set_id = ? "
    "ORDER BY created_at, ordinal LIMIT ? OFFSET ?"
)
FULL_READ_SQL = "SELECT payload FROM question_rows"


def build_rows(set_count: int, rows_per_set: int) -> list[tuple]:
    """Generate deterministic synthetic rows from arithmetic sequences."""
    rows = []
    for set_index in range(set_count):
        set_id = f"set-{set_index:04d}"
        for ordinal in range(rows_per_set):
            index = set_index * rows_per_set + ordinal
            created_at = (
                f"2024-{1 + index % 12:02d}-{1 + index % 28:02d}"
                f"T{index % 24:02d}:{index % 60:02d}:{index % 60:02d}"
            )
            stem = f"Simplify synthetic expression {index} and box the answer."
            body = {"difficulty": DIFFICULTIES[index % 3], "ordinal": ordinal, "stem": stem}
            payload = json.dumps(body, sort_keys=True)
            rows.append((set_id, ordinal, stem, body["difficulty"], created_at, payload))
    return rows


def timed_result(connection, label, action, sql, parameters, repeats):
    """Return (label, median milliseconds, query plan) for one action."""
    durations = []
    for _ in range(repeats):
        started = time.perf_counter()
        action()
        durations.append((time.perf_counter() - started) * 1000.0)
    planned = connection.execute("EXPLAIN QUERY PLAN " + sql, parameters)
    return label, statistics.median(durations), [row[3] for row in planned]


def scenario_ordered_scan(connection, target_set, repeats):
    """Compare a naive full scan plus sort with a composite-index scan."""
    connection.execute("DROP INDEX IF EXISTS idx_rows_set_created")
    connection.commit()

    def scan():
        return connection.execute(ORDERED_SCAN_SQL, (target_set,)).fetchall()

    naive = timed_result(
        connection, "full scan + sort", scan, ORDERED_SCAN_SQL, (target_set,), repeats
    )
    connection.execute(
        "CREATE INDEX idx_rows_set_created "
        "ON question_rows (set_id, created_at, ordinal)"
    )
    connection.commit()
    indexed = timed_result(
        connection, "composite index", scan, ORDERED_SCAN_SQL, (target_set,), repeats
    )
    return [naive, indexed]


def scenario_page_fetch(connection, target_set, page_size, page_index, repeats):
    """Compare a full read plus slice with a two-phase count-then-page query."""
    offset = page_index * page_size

    def full_read():
        every = connection.execute(FULL_READ_SQL).fetchall()
        return every[offset:offset + page_size]

    def two_phase_page():
        connection.execute(COUNT_SQL, (target_set,)).fetchone()
        return connection.execute(PAGE_SQL, (target_set, page_size, offset)).fetchall()

    return [
        timed_result(connection, "full read + slice", full_read, FULL_READ_SQL, (), repeats),
        timed_result(
            connection, "two-phase page", two_phase_page, PAGE_SQL,
            (target_set, page_size, offset), repeats
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sets", type=int, default=60, help="synthetic set count")
    parser.add_argument("--rows-per-set", type=int, default=1000, help="rows per set")
    parser.add_argument("--page-size", type=int, default=50, help="page row count")
    parser.add_argument("--page-index", type=int, default=7, help="page number")
    parser.add_argument("--repeats", type=int, default=5, help="runs per measurement")
    args = parser.parse_args(argv)

    connection = sqlite3.connect(":memory:")
    connection.execute(PROJECTION_SCHEMA)
    rows = build_rows(args.sets, args.rows_per_set)
    connection.executemany("INSERT INTO question_rows VALUES (?, ?, ?, ?, ?, ?)", rows)
    connection.commit()

    target_set = rows[-1][0]
    ordered = scenario_ordered_scan(connection, target_set, args.repeats)
    paged = scenario_page_fetch(
        connection, target_set, args.page_size, args.page_index, args.repeats
    )
    connection.close()

    print(
        "SQLite scaling benchmark (backs docs/sqlite-scaling.md)\n"
        f"rows={len(rows)} sets={args.sets} page_size={args.page_size} "
        f"page_index={args.page_index} repeats={args.repeats} (median ms)"
    )
    print(f"{'scenario':<24} {'mode':<18} {'median ms':>10} {'speedup':>9}  plan")
    for name, results in (("ordered scan of one set", ordered), ("page fetch", paged)):
        baseline = results[0][1]
        for label, elapsed, plan in results:
            print(
                f"{name:<24} {label:<18} {elapsed:>10.2f} "
                f"{baseline / elapsed:>8.1f}x  {'; '.join(plan)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
