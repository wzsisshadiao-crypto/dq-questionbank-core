"""Synthetic, in-memory regression checks for the SQLite scaling benchmark."""

from __future__ import annotations

import contextlib
import io
import sqlite3
import unittest

from scripts import bench_sqlite_scaling as benchmark


class SearchBenchmarkTests(unittest.TestCase):
    def test_search_markers_are_deterministic(self) -> None:
        rows = benchmark.build_rows(2, 100)
        self.assertEqual(rows, benchmark.build_rows(2, 100))
        self.assertEqual(
            3,
            sum(benchmark.SEARCH_TOKEN in row[2] for row in rows),
        )

    def test_fts_results_match_like_results(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(benchmark.PROJECTION_SCHEMA)
            connection.executemany(
                "INSERT INTO question_rows VALUES (?, ?, ?, ?, ?, ?)",
                benchmark.build_rows(2, 100),
            )
            result = benchmark.scenario_stem_search(connection, repeats=2)
            if result is None:
                self.skipTest("SQLite FTS5 is unavailable")
            matches, timings = result
            self.assertEqual(3, matches)
            self.assertEqual(["LIKE scan", "FTS5 MATCH"], [row[0] for row in timings])
            self.assertTrue(all(row[1] > 0 for row in timings))
        finally:
            connection.close()

    def test_missing_fts5_skips_only_search_comparison(self) -> None:
        class MissingFtsConnection:
            def execute(self, _statement: str) -> None:
                raise sqlite3.OperationalError("no such module: fts5")

        self.assertIsNone(benchmark.scenario_stem_search(MissingFtsConnection(), 1))

    def test_cli_reports_search_or_optional_skip(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = benchmark.main(
                ["--sets", "2", "--rows-per-set", "100", "--repeats", "1"]
            )
        self.assertEqual(0, status)
        self.assertIn("stem search", output.getvalue())


if __name__ == "__main__":
    unittest.main()
