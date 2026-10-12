# Optional stem phrase search in the local workspace

The visual workspace keeps each question set as its canonical JSON file in
`question_sets/`. Selecting **Stem phrase (FTS)** adds a distinct, opt-in
search mode. It does not migrate the JSON files or change the question schema.

The mode searches only question stems. On SQLite builds with FTS5, it matches
whole terms in the entered phrase using SQLite's default tokenizer. It is not
equivalent to the existing **Contains text** mode: a partial term such as
`cobal` can match `cobalt` with substring search but not FTS5 phrase search.
The existing mode remains the default and keeps its field scopes. Year,
subject, question-type, and recycle-bin filters still apply in the browser
after the FTS result IDs arrive. SQLite tokenization may not segment every
language as a reader expects, especially unsegmented CJK text; use Contains
text when phrase matching is not suitable.

## Cache lifecycle and fallback

The local server creates `.dq-stem-search-v1.sqlite3` in the selected
workspace on first FTS search. This sidecar contains derived stem text and
question IDs, so protect or back it up with the same care as the workspace.
It is not a source of truth and can be removed while the server is stopped;
the next search rebuilds it from canonical JSON. No private or production
database is read or migrated by the public package.

After an API save, the server marks that set's projection dirty and rebuilds
it on the next search. On a later server run, a changed JSON file's size or
nanosecond modification time also triggers a rebuild. External tools that
replace JSON while preserving *both* values should restart with the sidecar
removed to guarantee a fresh projection. A future index format can use a new
versioned filename without rewriting the canonical files.
On subsequent indexed searches, projections for JSON files removed outside
the app are pruned. When removing a collection containing sensitive content,
stop the server and remove the sidecar as well so no derived text remains
between searches.

If FTS5 is unavailable, the sidecar is unusable, the query has no token, or
SQLite cannot open the sidecar, the endpoint scans the canonical JSON stem
text with case-insensitive substring matching. Its response includes
`mode: "substring-fallback"`; the visual workspace labels this change. If
the search request itself fails, the already-loaded collection is searched
locally by stem substring and the interface reports that fallback. The
original Contains text mode never depends on SQLite.

The endpoint is loopback-only:

```text
GET /api/sets/{set_id}/stem-search?q=cobalt%20compass
{"ids": ["q-1"], "mode": "fts5-phrase"}
```

Input is bounded to 1-256 characters. The query is quoted as literal FTS
text, not accepted as FTS operators; set IDs still use the workspace's safe
identifier validation. Result IDs preserve question order. This endpoint
returns IDs only, not question payloads.

## Rollback

Switch the UI back to **Contains text** to use the previous behavior. The
canonical JSON remains unchanged. To discard a cache, stop the local server,
remove only the workspace's `.dq-stem-search-v1.sqlite3` sidecar after
verifying its exact path, then restart. Do not remove `question_sets/`.
