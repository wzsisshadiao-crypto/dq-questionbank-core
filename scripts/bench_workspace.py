"""Workspace performance benchmark backing the performance-budget practice.

Generates a deterministic synthetic workspace (filesystem sets plus a
SQLite mirror), then measures the load / scan / store / serialize paths
that dominate day-to-day use. Prints one timing table to stdout and exits
0; with ``--budget <json>`` it also fails (exit 1) when any measured
median exceeds its budget, so CI or a scheduled job can guard against
quiet regressions. Stdlib only; deterministic seed; no network, no deps.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from dq_questionbank.models import Content, ContentBlock, Question, QuestionSet
from dq_questionbank.quality_findings import detect_quality_findings
from dq_questionbank.sqlite_storage import SqliteStorageAdapter
from dq_questionbank.storage import FilesystemStorageAdapter

BENCH_VERSION = "bench-workspace/1"


def make_question(number: int) -> Question:
    parity = "even" if number % 2 == 0 else "odd"
    return Question(
        id=f"q-{number:06d}",
        type="short_answer",
        stem=Content(
            [
                ContentBlock(
                    type="text", text=f"Question {number}: compute the {parity} case."
                ),
                ContentBlock(type="math", latex=f"x_{{{number}}} + 1 = {number}"),
            ]
        ),
        tags=[parity, f"batch-{number // 100}"],
    )


def build_workspace(root: Path, set_count: int, per_set: int) -> list[QuestionSet]:
    sets = [
        QuestionSet(
            id=f"bench-set-{index:03d}",
            title=f"Benchmark set {index}",
            questions=[make_question(index * per_set + offset) for offset in range(per_set)],
        )
        for index in range(set_count)
    ]
    storage = FilesystemStorageAdapter(root)
    for question_set in sets:
        storage.save(question_set)
    return sets


def timed_median(action, repeats: int) -> float:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        action()
        samples.append(time.perf_counter() - started)
    return statistics.median(samples)


def run_benchmarks(questions_total: int, set_count: int, repeats: int) -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        sets = build_workspace(root, set_count, questions_total // set_count)
        storage = FilesystemStorageAdapter(root)
        database = root / "bench.db"
        sqlite = SqliteStorageAdapter(database)
        for question_set in sets:
            sqlite.save(question_set)

        def load_all() -> None:
            for question_set in sets:
                storage.load(question_set.id)

        def scan_all() -> None:
            for question_set in sets:
                for question in question_set.questions:
                    detect_quality_findings(question)

        def sqlite_load_all() -> None:
            for question_set in sets:
                sqlite.load(question_set.id)

        def serialize_all() -> None:
            for question_set in sets:
                json.dumps(question_set.to_dict(), ensure_ascii=False)

        try:
            return {
                "version": BENCH_VERSION,
                "questions": questions_total,
                "sets": set_count,
                "repeats": repeats,
                "filesystem_load_seconds": round(timed_median(load_all, repeats), 4),
                "sqlite_load_seconds": round(timed_median(sqlite_load_all, repeats), 4),
                "quality_scan_seconds": round(timed_median(scan_all, 1), 4),
                "json_serialize_seconds": round(timed_median(serialize_all, repeats), 4),
            }
        finally:
            sqlite.close()


def check_budgets(results: dict, budget: dict) -> list[str]:
    failures = []
    for key, limit in budget.items():
        measured = results.get(key)
        if isinstance(measured, (int, float)) and measured > float(limit):
            failures.append(f"{key}: {measured}s exceeds budget {limit}s")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=int, default=1000)
    parser.add_argument("--sets", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--budget", type=Path, help="JSON file of ceiling seconds")
    args = parser.parse_args(argv)

    results = run_benchmarks(args.questions, args.sets, args.repeats)
    print(f"workspace benchmark v{results['version']}")
    print(f"questions={results['questions']} sets={results['sets']} repeats={results['repeats']}")
    for key in (
        "filesystem_load_seconds",
        "sqlite_load_seconds",
        "quality_scan_seconds",
        "json_serialize_seconds",
    ):
        print(f"{key:26s} {results[key]:>10.4f} s (median)")

    if args.budget and args.budget.is_file():
        budget = json.loads(args.budget.read_text(encoding="utf-8"))
        failures = check_budgets(results, budget)
        for failure in failures:
            print(f"BUDGET EXCEEDED {failure}")
        if failures:
            return 1
        print("All budgets satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
