# Read-Only Workspace Health Audit

A local-first workspace keeps canonical JSON question sets under
`<root>/question_sets/` and asset files under an assets root of your
choosing. Edits made outside the reviewed tools can leave the workspace
subtly inconsistent; these three read-only checks surface the drift.
This is the workflow tracked in
[issue #99](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues/99).

## The read-only contract

- An audit only reads: it never writes, moves, renames, or deletes
  workspace files, and never opens a database read-write.
- A check reports what it finds and exits. Fixing is always a separate,
  explicit, reviewed step.
- Nothing here repairs anything, and repair behavior must never be
  wired into an audit silently.

## Scope and honest limits

The checks target the layout shared by the visual workspace and
[`FilesystemStorageAdapter`](filesystem-storage.md). There is no
`dq audit` subcommand today: check 1 uses the real `dq validate`
command (after an editable install, see
[../CONTRIBUTING.md](../CONTRIBUTING.md)), while checks 2 and 3 are
short snippets over the public Python API
([`QuestionSet`](question-schema.md) and the storage adapters).
Checks 1 and 2 share this read-only loader, saved beside your scripts
as `audit_common.py`:

```python
# audit_common.py - shared read-only helpers for the checks below
from pathlib import Path

from dq_questionbank import FilesystemStorageAdapter


def all_questions(root):
    """Yield (question_set, question); unreadable files are reported."""
    storage = FilesystemStorageAdapter(root)
    for path in sorted((root / "question_sets").glob("*.json")):
        try:
            question_set = storage.load(path.stem)
        except (OSError, TypeError, ValueError) as exc:
            print(f"UNREADABLE {path.name}: {exc}")
            continue
        stack = list(question_set.questions)
        while stack:
            question = stack.pop()
            stack.extend(question.subquestions)
            yield question_set, question


def is_file_uri(uri):
    """Relative-path URIs are files; HTTPS and data: URIs are not."""
    return "://" not in uri and not uri.startswith("data:")
```

`storage.load()` fails closed on corrupt JSON and on a stored id that
does not match its file name, so both surface as `UNREADABLE` lines in
any check using the loader.

## Check 1: broken references

What it detects, in two layers:

- Inside a set: an image block whose `asset_id` is not declared in that
  question's `assets`, an answer pointing at a missing choice id,
  duplicate or unsafe asset ids. Subquestions are included.
- On disk: a declared asset whose relative URI resolves to no file
  under the assets root.

Layer one is one command per stored set. A healthy set exits 0 with the
first line below; each problem adds one line and exits 1:

```bash
dq validate path/to/workspace/question_sets/set-id.json
```

```text
Valid: 10 question(s), schema 1.1.
ERROR questions[1].stem.blocks[1]: Image blocks require asset_id. [missing_asset_id]
```

Layer two needs the Python API, because `dq validate` checks references
without looking at the disk:

```python
import sys
from pathlib import Path

from audit_common import all_questions, is_file_uri

root, assets_root = (Path(arg) for arg in sys.argv[1:3])
for question_set, question in all_questions(root):
    for asset in question.assets:
        if is_file_uri(asset.uri) and not (assets_root / asset.uri).is_file():
            print(f"MISSING {question_set.id}/{question.id} {asset.id} {asset.uri}")
```

A problem looks like:

```text
MISSING set-id/question-3 img-01 assets/question-3/img-01.png
```

## Check 2: orphan assets

What it detects: files under the assets root referenced by no question
in any stored set - debris from edits, renames, or aborted imports.
HTTPS and `data:` URIs live outside the root and cannot be matched.

```python
import sys
from pathlib import Path

from audit_common import all_questions, is_file_uri

root, assets_root = (Path(arg) for arg in sys.argv[1:3])
referenced = {
    (assets_root / asset.uri).resolve()
    for _, question in all_questions(root)
    for asset in question.assets
    if is_file_uri(asset.uri)
}
for file in sorted(p for p in assets_root.rglob("*") if p.is_file()):
    if file.resolve() not in referenced:
        print(f"ORPHAN {file.relative_to(assets_root).as_posix()}")
```

A healthy workspace prints nothing; a problem looks like:

```text
ORPHAN question-3/old-diagram.png
```

An orphan is a deletion candidate, never an automatic deletion: a set
outside this workspace, or an import still in flight, may use it.

## Check 3: derived-index sync

What it detects: disagreement between a stored SQLite row and the data
it derives from. [`SqliteStorageAdapter`](sqlite-storage.md) writes
each set as one `question_sets` row: the canonical payload plus
`schema_version` and `question_count`, both copied from the payload in
the same save transaction. Drift therefore means the database was
edited outside the adapter.

The adapter itself opens read-write and creates the table when missing,
so a strict audit opens the file read-only via a `mode=ro` URI and
re-derives both columns from each payload:

```python
import json
import sqlite3
import sys
from pathlib import Path

from dq_questionbank import QuestionSet

database = Path(sys.argv[1]).resolve().as_posix()
connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
rows = connection.execute(
    "SELECT id, payload, schema_version, question_count"
    " FROM question_sets"
).fetchall()
connection.close()

for row_id, payload, schema_version, question_count in rows:
    question_set = QuestionSet.from_dict(json.loads(payload))
    if question_set.id != row_id:
        print(f"DRIFT {row_id}: payload declares id {question_set.id}")
    if question_set.schema_version != schema_version:
        print(f"DRIFT {row_id}: schema_version {schema_version}"
              f" != {question_set.schema_version}")
    if len(question_set.questions) != question_count:
        print(f"DRIFT {row_id}: question_count {question_count}"
              f" != {len(question_set.questions)}")
```

A healthy database prints nothing; drift prints lines like:

```text
DRIFT set-id: question_count 10 != 9
```

`load()` already fails closed on a payload whose id differs from its
row, but it does not re-check the two derived columns. If you also
mirror sets in a filesystem workspace, diff the row ids against the
`question_sets/*.json` file stems.

## When a check finds something

1. Change nothing from inside the audit; keep the output as evidence.
2. Make the fix reversible first: run the verified backup drill in
   [backup-restore.md](backup-restore.md).
3. Repair through explicit, reviewable tooling: image replacement via
   the digest-bound contract in [asset-repair.md](asset-repair.md),
   other drift by editing the source and re-saving through an adapter.
4. Re-run the audit; a fix is done when the check is silent.
5. If the core tools look at fault rather than the data,
   [open an issue](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues)
   with the audit output attached.

Reporting and repairing are different operations, run by different
code, at different times. Keep the boundary.
