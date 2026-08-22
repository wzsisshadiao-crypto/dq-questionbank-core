# Reviewable Import Candidate Sessions

This document describes the public contract for reviewable import
candidate sessions — the boundary between source extraction and
persistence. It ships as `dq_questionbank.review_session` over the
digest-bound session documents produced by `dq_questionbank.intake`.

## The contract

An **`ImportCandidateSession`** wraps one canonical session document:

- **Extraction, not acceptance.** A freshly prepared session holds
  candidates with `decision: "pending"`. No state in the contract implies
  persistence or AI approval.
- **Parser identity and source evidence are retained.** The session keeps
  the parser identity (`parser.identity`, default `canonical-records/1`)
  next to the source reference and per-candidate evidence excerpts.
- **Deterministic revisions.** Every candidate starts at `revision: 1`.
  When a reviewed edit replaces its payload, the revision bumps and the
  candidate digest is rebound; accepts and rejects without edits keep the
  revision unchanged.
- **Explicit states.** `decide({"decisions": [...]})` moves candidates
  from `pending` to `accepted` or `rejected` and fails closed on stale
  digests, already-reviewed candidates, or invalid edits. The session
  status moves `candidate_ready` → `in_review` → `reviewed`.
- **Export, not persistence.** `export_accepted()` returns a canonical
  `QuestionSet` of accepted candidates only, and requires every candidate
  to have an explicit decision. It never writes to a store.

`from_session` verifies the digest before wrapping; `to_session`
reproduces the canonical document exactly, so typed views never drift
from the wire format.

## Extending with source-specific import profiles

A source-specific pipeline extends the contract without changing it:

1. **Produce the same session shape.** Extract candidates with your own
   parser, set `parser.identity` to a stable name for it, and attach
   evidence excerpts per candidate. Digests bind the result.
2. **Decide through the same API.** Accept, reject, and edit through
   `decide` so staleness and revision rules stay uniform across routes.
3. **Export, then persist on your side.** Call `export_accepted()` and
   store the result with your own adapter (for example
   `SqliteStorageAdapter`); the contract itself stays storage-neutral.

Bounded proposals (including AI-assisted ones) ride along as session
metadata marked `requires_human_review` — they never change a candidate
until a human decision applies them.

## Fixtures

Stable serialized examples — pending, reviewed (accepted with edit,
revision 2), rejected, and the exported question set — live in
`tests/fixtures/review-sessions/` and are executed by
`tests/test_review_session.py`.
