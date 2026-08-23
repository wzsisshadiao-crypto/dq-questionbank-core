"""Deterministic, collision-checked id allocation for questions and sets.

Allocation is a pure decision: the caller owns persistence, this helper
owns only the choice of the next free id. Given the same set of existing
ids and the same preferred id, the result is always identical — no
timestamps, no counters hidden in storage, no randomness — so allocation
is testable and race-free by construction.

Preferred ids are normalized (lowercased, trimmed, internal whitespace
runs collapsed to single ``-``) and never encode volatile fields: ids
derived from titles or dates would silently break references when the
title changes. Collisions resolve through a bounded, documented suffix
scheme (``-2``, ``-3``, … ``-99``); exhausting the bound raises
``ValueError`` so callers fail closed instead of inventing an unbounded
id. Design guidance lives in ``docs/question-id-design.md`` (issue #98).

Clean-room implementation from synthetic fixtures; part of issue #88.
"""

from __future__ import annotations

import re

ID_ALLOCATION_VERSION = "id-allocation/1"

DEFAULT_QUESTION_BASE = "question"
DEFAULT_SET_BASE = "set"

# Collisions append -2 .. -99; past the bound allocation fails closed.
MIN_COLLISION_SUFFIX = 2
MAX_COLLISION_SUFFIX = 99

_UNSAFE_CHARS = re.compile(r"[^a-z0-9\-_]")
_WHITESPACE_RUN = re.compile(r"\s+")


def normalize_preferred_id(preferred: str | None) -> str:
    """Normalize a reviewer-supplied preferred id.

    The rule is deterministic: lowercase, trim, collapse internal
    whitespace runs to a single ``-``, then drop every character outside
    ``[a-z0-9-_]``. An input that normalizes to nothing yields ``""`` and
    the caller falls back to the default base.
    """
    if not isinstance(preferred, str):
        return ""
    collapsed = _WHITESPACE_RUN.sub("-", preferred.strip().lower())
    return _UNSAFE_CHARS.sub("", collapsed).strip("-")


def _allocate(existing_ids, preferred: str | None, default_base: str) -> str:
    existing = {str(item) for item in existing_ids}
    preferred_id = normalize_preferred_id(preferred)
    if not preferred_id:
        # Default allocation is always numbered so ids stay predictable as
        # a bank grows: question-1, question-2, …
        for number in range(1, MAX_COLLISION_SUFFIX + 1):
            candidate = f"{default_base}-{number}"
            if candidate not in existing:
                return candidate
        raise ValueError(
            f"Id allocation for {default_base!r} exhausted its bound of "
            f"{MAX_COLLISION_SUFFIX} candidates; ids never grow unbounded."
        )
    if preferred_id not in existing:
        return preferred_id
    for suffix in range(MIN_COLLISION_SUFFIX, MAX_COLLISION_SUFFIX + 1):
        candidate = f"{preferred_id}-{suffix}"
        if candidate not in existing:
            return candidate
    raise ValueError(
        f"Id allocation for {preferred_id!r} exhausted its bound of "
        f"{MAX_COLLISION_SUFFIX} candidates; ids never grow unbounded."
    )


def allocate_question_id(existing_ids, preferred: str | None = None) -> str:
    """Return the next free question id (pure, collision-checked)."""
    return _allocate(existing_ids, preferred, DEFAULT_QUESTION_BASE)


def allocate_set_id(existing_ids, preferred: str | None = None) -> str:
    """Return the next free question-set id (pure, collision-checked)."""
    return _allocate(existing_ids, preferred, DEFAULT_SET_BASE)
