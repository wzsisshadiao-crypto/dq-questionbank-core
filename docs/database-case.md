# Public database cases

The visual workspace can present a small, reviewed SQLite question-bank case.
The bundled case is synthetic. A future real-content case uses the same adapter
but requires an independent publication review.

## User workflow

Run `python run.py`, then choose **Open public case**. The application opens
the source database read-only, converts its public fields to canonical schema
`1.0`, and saves a JSON copy in the selected workspace. Visual edits affect
that JSON copy only. The Question Bank view supports collection and question
navigation, text search, year, subject and type filters, offline math rendering,
structured tables, answer and solution review, editing, paper assembly, local
quality checks, collection metrics, and canonical paper export.

To use a separately downloaded case:

```bash
dq-local --workspace ./workspace --case-database ./downloaded-case.sqlite3
```

The adapter rejects symbolic links, malformed SQLite files, unsupported table
layouts, cases without public license and provenance metadata, and cases above
2,000 questions. SQLite is opened with `mode=ro`, `immutable=1`, and
`PRAGMA query_only`.

## Supported tables

The `questions` table requires `question_id`, `subject_attribute`,
`question_type`, and `body_chinese`. The adapter also reads these optional
public columns when present:

- `grade`, `question_format`, `question_category`, and `source_year`
- `source_chinese` and `source_english`
- `body_english`
- `body_blocks_json`, an optional canonical content-block array for formulas,
  tables, code, and mixed-language question stems
- `answer_chinese` and `answer_english`
- `analysis_chinese` and `analysis_english`
- `solutions_chinese` and `solutions_english`

An optional `question_options` table must contain `question_id`, `option_label`,
`option_chinese`, `option_english`, and `is_correct`.

A case database must include one `dq_case_metadata` row with `case_id`, `title`,
`description`, `language`, `license`, and `provenance`. These values are shown
in the UI and carried into canonical metadata. The adapter selects localized
question, option, answer, solution, and source fields using this language. The
bundled case is English-first, so its visual workspace never mixes the legacy
Chinese compatibility columns into the displayed questions.

## Publication checklist

1. Select a small allowlist of questions with confirmed redistribution rights.
2. Build a brand-new SQLite file containing only the documented public columns.
3. Do not sanitize by deleting rows or columns from a production database.
   Deleted SQLite pages can retain recoverable private content.
4. Exclude operators, users, timestamps, internal review state, logs, media
   paths, provider data, maintenance tables, and deployment information.
5. Review every question, answer, solution, source, license, and attribution.
6. Verify that only the expected tables, indexes, and metadata exist and that
   `PRAGMA freelist_count` is zero.
7. Run the adapter and canonical schema tests against the final artifact.
8. Record the file size, SHA-256 checksum, schema version, content count,
   license, and provenance in the release notes.

The production database is never an acceptable release artifact, even if it
appears to contain only a few public rows.

## Bundled synthetic case

`examples/synthetic-case-source.json` is the reviewable source for the bundled
database. `scripts/build_case_database.py` creates
`src/dq_questionbank_local/data/synthetic-case.sqlite3` atomically. Tests compare
their canonical meaning and verify that reading the database does not modify it.
The bundled case contains ten original synthetic questions across seven
mathematics subject labels, six canonical question types, and several source years.
It includes a structured 9-by-9 Cayley table, inline and block-ready LaTeX,
single- and multiple-choice questions, and complete answers and solutions. This
provides enough variation to exercise the workspace filters, metrics, paper
assembly, editor, deterministic quality checks, and responsive rendering. All
bundled questions are presented in English.
