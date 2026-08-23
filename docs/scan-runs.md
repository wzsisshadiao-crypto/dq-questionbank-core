# Resumable Batch Scan Runs

This document describes the recoverable batch-scan orchestration shipped in
`dq_questionbank.quality_scan_runs` (part of #95). A scan over thousands of
questions must survive interruption without rescanning from zero and without
losing results. The module is orchestration state only — detection itself is
the public contract in [Revision-Bound Quality Findings](quality-findings.md).

## The crash-survival contract

A scan run is a small immutable value, `ScanRunState`:

- `run_id` — a stable id; `start_run` derives a deterministic
  `scan-<digest>` id from the ordered unique question ids when none is
  supplied, so restarting the same scope yields the same run id without a
  counter or a clock;
- `question_ids` — the ordered scope, deduplicated in first-seen order;
- `completed` — the scanned ids in completion order, always duplicate-free;
- `failures` — one entry per (question, failing rule); rule ids come from
  the public `quality/1` vocabulary and are only passed through, never
  invented here;
- `lease` — optional exclusive ownership, `None` until a caller attaches
  one.

Every operation is pure — no I/O, no wall clock, no randomness. The
crash-survival contract is therefore a loop the caller owns:

1. `start_run(question_ids, lease)` opens the run;
2. `checkpoint(run, question_id, failed_rules=...)` records each scanned
   question exactly once;
3. the caller persists `run.to_dict()` after each checkpoint (JSON now, a
   table via `dq_questionbank.sqlite_storage` later) — the module never
   touches storage itself;
4. after a crash, `ScanRunState.from_dict` rebuilds the exact same state
   and `pending_items` tells the worker where to continue.

`checkpoint` fails closed: an unknown question id or an already-completed
id raises `ValueError`, so a replayed checkpoint can neither duplicate work
nor smuggle in results. `from_dict` re-validates everything (unique ids,
completed ids inside the scope, failures referencing only in-run questions)
and rejects unknown fields.

## Leases: deterministic expiry

`resume_run(run, now_tick=..., lease=...)` installs a fresh lease when
ownership is free. A lease is `ScanLease(lease_id, owner, expires_at)`;
expiry is anchored to a monotonic tick counter supplied by the caller,
never wall time, so every resume decision is deterministic and replayable
in fixtures. A lease is expired exactly when `now_tick >= expires_at`.

| Old lease at `now_tick` | New owner | Result |
|---|---|---|
| none | any | lease installed |
| `now_tick >= expires_at` | any | expired lease replaced |
| `now_tick < expires_at` | same owner | early renewal, lease replaced |
| `now_tick < expires_at` | another owner | `LeaseHeldError` (fail closed) |

Refusing to resume is always preferable to silently double-scanning, which
is why the held case raises instead of overwriting.

## Persistence recipe

State is pure data with strict `to_dict` / `from_dict` round-trips, so any
JSON store works — the caller decides where the bytes live:

```python
import json

from dq_questionbank.quality_scan_runs import ScanRunState

# after each checkpoint (or on a clean shutdown)
blob = json.dumps(run.to_dict())          # JSON-safe plain data

# after a crash or a restart
run = ScanRunState.from_dict(json.loads(blob))
```

`to_dict` emits plain lists and dicts; `from_dict` validates the payload
and raises `ValueError` on unknown fields, duplicate ids, or failures that
reference questions outside the run — a corrupted snapshot fails loudly
instead of resuming from a lie.

## Recipe: survive an interruption

```python
from dq_questionbank.quality_scan_runs import (
    LeaseHeldError, ScanLease, checkpoint, pending_items, resume_run,
    start_run, summarize,
)

lease = ScanLease(lease_id="lease-1", owner="worker-a", expires_at=100)
run = start_run(["q-1", "q-2", "q-3"], lease)
run = checkpoint(run, "q-1")
run = checkpoint(run, "q-2", failed_rules=("latex-mismatched-delimiters",))
# run_id: scan-65347e995167 (deterministic, derived from the scope)

# ... the process dies here; only the persisted to_dict() survives ...

# worker-b resumes once the old lease is expired (now_tick >= expires_at):
run = resume_run(
    run, now_tick=100,
    lease=ScanLease(lease_id="lease-2", owner="worker-b", expires_at=200),
)
pending_items(run)                          # ('q-3',) — exactly-once

# a third owner while the lease is live fails closed:
try:
    resume_run(
        run, now_tick=150,
        lease=ScanLease(lease_id="lease-3", owner="worker-c", expires_at=260),
    )
except LeaseHeldError as error:
    ...  # leased to 'worker-b' until tick 200

run = checkpoint(run, "q-3")
summarize(run)
```

The final `summarize(run)` returns:

```python
{
    "run_id": "scan-65347e995167",
    "total": 3,
    "completed": 3,
    "pending": 0,
    "coverage_complete": True,
    "failures_by_rule": {"latex-mismatched-delimiters": 1},
    "ruleset": "quality/1",
}
```

`failures_by_rule` counts one entry per (question, failing rule), keyed by
the `quality/1` rule ids the caller supplied at checkpoint time, so the
summary drops straight into the same rule vocabulary the Quality Center
already displays.
