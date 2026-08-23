# Safe Backup-and-Restore Drill

The local-first workflow keeps question collections on the user's own
disk. Before a bulk edit - a quality repair pass, a metadata rewrite, an
import experiment - make the operation reversible by drilling a verified
backup first.

[`examples/backup_restore_drill.py`](../examples/backup_restore_drill.py)
runs four phases on a workspace directory you choose, using only the
Python standard library:

```bash
python examples/backup_restore_drill.py --workspace path/to/workspace
```

## When to back up

- before applying a batch of edits to a stored collection (quality
  repairs, renames, metadata changes);
- before trying a new import or export flow against a real workspace;
- any time an operation looks destructive and you have not run it
  against this data before.

Run the drill against a **synthetic sample workspace**, never against
production or private data.

## What a verified backup contains

- a copy of every regular file under the workspace (symlinks are skipped
  and never written through);
- a `manifest.json` with each file's relative path and SHA-256 digest.

Verification re-digests every manifest entry and fails closed on any
mismatch, a missing file, or an unmanifested extra file. A backup is only
trusted after verification passes.

## Restore without losing later edits

The drill's restore phase copies the verified files back and then
re-digests the workspace, proving it is byte-identical to the pre-drill
state. Exit code `0` means every phase passed; any mismatch exits
non-zero with a message on stderr.

Because restore only proceeds from a **verified** manifest, a tampered or
corrupted backup is rejected before anything is overwritten. Later edits
made after the backup are overwritten by a restore - that is the point of
the drill - so take a fresh backup immediately before the operation you
want to make reversible.

## Safety notes

- The script never follows or writes through symbolic links.
- An existing backup directory is refused rather than merged into.
- A focused test in `tests/test_backup_restore.py` exercises the drill
  end to end on a temporary workspace, including the tampered-backup
  failure path.
