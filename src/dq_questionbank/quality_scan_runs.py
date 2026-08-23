"""Recoverable batch-scan orchestration — lease, checkpoint, resume, and
summarize; a scan over thousands of questions must survive interruption
without rescanning from zero and without losing results. Part of #95.

A scan run is a small immutable value: the ordered question ids in scope,
the ids already scanned (in completion order), one failure entry per
(question, failing rule), and the optional lease guarding exclusive
ownership. Every operation here is pure — no I/O, no wall clock, no
randomness — so a caller can persist ``to_dict()`` output after each
checkpoint (JSON now, a table via :mod:`dq_questionbank.sqlite_storage`
later) and rebuild the exact same state with ``from_dict`` after a crash:

- ``start_run`` opens a run, deduplicating ids while preserving order and
  deriving a deterministic run id from the run's content when none is
  supplied;
- ``checkpoint`` records one scanned item exactly once and appends one
  failure entry per failing rule id — rule ids come from the public
  ``quality/1`` vocabulary (see :mod:`dq_questionbank.quality_findings`)
  and are only passed through, never invented here;
- ``resume_run`` fails closed with :class:`LeaseHeldError` while a live
  lease belongs to another owner, and otherwise installs the fresh lease;
- ``pending_items`` and ``summarize`` report exactly-once progress.

Lease expiry is anchored to a monotonic tick counter supplied by the
caller, never wall time: a lease is expired exactly when
``now_tick >= lease.expires_at``, which keeps every resume decision
deterministic and replayable in fixtures.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .quality_findings import RULESET_VERSION

SCAN_RUN_VERSION = "scan-run/1"

_LEASE_FIELDS = {"lease_id", "owner", "expires_at"}
_RUN_FIELDS = {"run_id", "question_ids", "completed", "failures", "lease"}
_FAILURE_FIELDS = {"question_id", "rule_id", "error"}


class ScanRunError(RuntimeError):
    """Base class for scan-run orchestration failures."""


class LeaseHeldError(ScanRunError):
    """Resume refused: an unexpired lease is still held by another owner."""


def _canonical_json(value: Any) -> str:
    """Return the canonical JSON form used for deterministic digests."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _require_id(value: Any, label: str) -> str:
    """Return ``value`` as a non-empty string or fail closed."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string, got {value!r}.")
    return value


def _dedupe_preserving_order(values: Iterable[str]) -> tuple[str, ...]:
    """Return the unique values in first-seen order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)



def _copy_failure(entry: Any, *, question_ids: set[str]) -> dict[str, Any]:
    """Validate and copy one serialized failure entry."""
    if not isinstance(entry, dict):
        raise ValueError(f"Each scan-run failure must be a mapping, got {entry!r}.")
    unknown = sorted(set(entry) - _FAILURE_FIELDS)
    if unknown:
        raise ValueError(f"Unknown scan-failure field(s): {', '.join(unknown)}.")
    missing = sorted(_FAILURE_FIELDS - set(entry))
    if missing:
        raise ValueError(f"Scan-failure entry missing field(s): {', '.join(missing)}.")
    question_id = _require_id(entry["question_id"], "failure question_id")
    rule_id = _require_id(entry["rule_id"], "rule_id")
    if question_id not in question_ids:
        raise ValueError(f"Failure references question {question_id!r} outside the run.")
    return {"question_id": question_id, "rule_id": rule_id, "error": str(entry["error"])}


@dataclass(frozen=True, slots=True)
class ScanLease:
    """Exclusive ownership of a scan run, anchored to a tick counter.

    ``expires_at`` is a monotonic tick supplied by the caller, never wall
    time, so lease decisions stay deterministic: a lease is expired
    exactly when ``now_tick >= expires_at``.
    """

    lease_id: str
    owner: str
    expires_at: int

    def is_expired(self, now_tick: int) -> bool:
        """Return whether the lease is expired at ``now_tick``."""
        return now_tick >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "owner": self.owner,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanLease:
        unknown = sorted(set(data) - _LEASE_FIELDS)
        if unknown:
            raise ValueError(f"Unknown scan-lease field(s): {', '.join(unknown)}.")
        expires_at = data["expires_at"]
        if isinstance(expires_at, bool) or not isinstance(expires_at, int):
            raise ValueError(
                f"lease expires_at must be an integer tick, got {expires_at!r}."
            )
        return cls(
            lease_id=_require_id(data["lease_id"], "lease_id"),
            owner=_require_id(data["owner"], "owner"),
            expires_at=expires_at,
        )



@dataclass(frozen=True, slots=True)
class ScanRunState:
    """Immutable, serializable state of one batch quality-scan run.

    ``completed`` holds the scanned ids in completion order and is always
    duplicate-free (exactly-once semantics); ``failures`` holds one entry
    per (question, failing rule) with rule ids from the public ``quality/1``
    vocabulary. ``lease`` is ``None`` until a caller attaches one.
    """

    run_id: str
    question_ids: tuple[str, ...]
    completed: tuple[str, ...]
    failures: tuple[dict[str, Any], ...]
    lease: ScanLease | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "question_ids": list(self.question_ids),
            "completed": list(self.completed),
            "failures": [dict(entry) for entry in self.failures],
            "lease": self.lease.to_dict() if self.lease is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanRunState:
        unknown = sorted(set(data) - _RUN_FIELDS)
        if unknown:
            raise ValueError(f"Unknown scan-run field(s): {', '.join(unknown)}.")
        question_ids = tuple(
            _require_id(item, "question id") for item in data["question_ids"]
        )
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("Scan-run question ids must be unique; start_run dedupes.")
        known = set(question_ids)
        completed = tuple(_require_id(item, "completed id") for item in data["completed"])
        if len(set(completed)) != len(completed):
            raise ValueError("Scan-run completed ids must be unique (exactly-once).")
        stray = [item for item in completed if item not in known]
        if stray:
            raise ValueError(f"Completed ids outside the run: {', '.join(stray)}.")
        failures = tuple(
            _copy_failure(entry, question_ids=known) for entry in data["failures"]
        )
        lease_data = data["lease"]
        lease = None if lease_data is None else ScanLease.from_dict(lease_data)
        return cls(
            run_id=_require_id(data["run_id"], "run_id"),
            question_ids=question_ids,
            completed=completed,
            failures=failures,
            lease=lease,
        )



def start_run(
    question_ids: Iterable[str],
    lease: ScanLease | None,
    run_id: str = "",
) -> ScanRunState:
    """Open a scan run over ``question_ids``, deduplicated in first-seen order.

    An empty ``run_id`` derives a deterministic id from the run's content
    (the ordered unique ids), so restarting the same scan yields the same
    run id without any counter or clock.
    """
    if lease is not None and not isinstance(lease, ScanLease):
        raise ValueError(f"lease must be a ScanLease or None, got {lease!r}.")
    unique_ids = _dedupe_preserving_order(
        _require_id(item, "question id") for item in question_ids
    )
    if not run_id:
        digest = hashlib.sha256(
            _canonical_json({"question_ids": list(unique_ids)}).encode("utf-8")
        ).hexdigest()
        chosen_id = f"scan-{digest[:12]}"
    else:
        chosen_id = _require_id(run_id, "run_id")
    return ScanRunState(
        run_id=chosen_id,
        question_ids=unique_ids,
        completed=(),
        failures=(),
        lease=lease,
    )


def pending_items(run: ScanRunState) -> tuple[str, ...]:
    """Return the ids not yet completed, in run order (exactly-once helper)."""
    done = set(run.completed)
    return tuple(item for item in run.question_ids if item not in done)


def checkpoint(
    run: ScanRunState,
    question_id: str,
    *,
    failed_rules: Iterable[str] = (),
) -> ScanRunState:
    """Record one scanned question exactly once, appending failure entries.

    Unknown ids and already-completed ids raise ``ValueError`` so a replayed
    checkpoint can never duplicate work or smuggle in results. Each rule id
    in ``failed_rules`` contributes one failure entry; ids are deduplicated
    per question while preserving order, and must be non-empty strings from
    the public rule vocabulary (they are only passed through here).
    """
    question_id = _require_id(question_id, "question id")
    if question_id not in run.question_ids:
        raise ValueError(f"Question {question_id!r} is not part of run {run.run_id!r}.")
    if question_id in run.completed:
        raise ValueError(
            f"Question {question_id!r} is already completed in run {run.run_id!r}; "
            "each item is checkpointed exactly once."
        )
    rules = _dedupe_preserving_order(
        _require_id(rule_id, "rule_id") for rule_id in failed_rules
    )
    failures = run.failures + tuple(
        {
            "question_id": question_id,
            "rule_id": rule_id,
            "error": f"Rule {rule_id} flagged question {question_id}.",
        }
        for rule_id in rules
    )
    return ScanRunState(
        run_id=run.run_id,
        question_ids=run.question_ids,
        completed=run.completed + (question_id,),
        failures=failures,
        lease=run.lease,
    )



def resume_run(run: ScanRunState, *, now_tick: int, lease: ScanLease) -> ScanRunState:
    """Return the state with ``lease`` installed when ownership is free.

    The old lease counts as held exactly while ``now_tick < expires_at``:
    an absent or expired lease is simply replaced, an unexpired lease held
    by another owner raises :class:`LeaseHeldError` (fail closed rather
    than silently double-scanning), and the same owner may renew early.
    """
    if not isinstance(lease, ScanLease):
        raise ValueError(f"lease must be a ScanLease, got {lease!r}.")
    if isinstance(now_tick, bool) or not isinstance(now_tick, int):
        raise ValueError(f"now_tick must be an integer tick, got {now_tick!r}.")
    current = run.lease
    if current is not None and not current.is_expired(now_tick):
        if current.owner != lease.owner:
            raise LeaseHeldError(
                f"Run {run.run_id!r} is leased to {current.owner!r} until tick "
                f"{current.expires_at}; owner {lease.owner!r} may not resume."
            )
    return ScanRunState(
        run_id=run.run_id,
        question_ids=run.question_ids,
        completed=run.completed,
        failures=run.failures,
        lease=lease,
    )


def summarize(run: ScanRunState) -> dict[str, Any]:
    """Return the coverage and per-rule failure summary of a run.

    ``coverage_complete`` is true when nothing is pending (an empty run is
    vacuously complete); ``failures_by_rule`` counts failure entries per
    rule id, keyed by the public ``quality/1`` rule vocabulary the caller
    supplied at checkpoint time.
    """
    failures_by_rule: dict[str, int] = {}
    for entry in run.failures:
        rule_id = str(entry["rule_id"])
        failures_by_rule[rule_id] = failures_by_rule.get(rule_id, 0) + 1
    pending = pending_items(run)
    return {
        "run_id": run.run_id,
        "total": len(run.question_ids),
        "completed": len(run.completed),
        "pending": len(pending),
        "coverage_complete": not pending,
        "failures_by_rule": failures_by_rule,
        "ruleset": RULESET_VERSION,
    }
