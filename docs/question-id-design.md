# Question-id Design

Questions and question sets carry plain string identifiers -
`Question(id=...)` and `QuestionSet(id=...)` in the [schema](question-schema.md).
Models generate no ids; whoever constructs a question picks one, usually
through the allocation helper described below.

A bank is long-lived: files are named after set ids in
[filesystem storage](filesystem-storage.md) and keyed by ids in
[SQLite](sqlite-storage.md), while review notes, exports, and fixtures cite
ids by hand. Every such reference ages exactly as fast as the ids it cites,
so an id is a promise that outlives any single question. Three rules keep
that promise: never encode volatile fields, normalize consistently, and
never reuse a retired id.

## Never encode volatile fields

An id must survive every edit a reviewer can make to the question. Anything
derived from mutable content - dates, titles, positions, difficulty - breaks
the id the moment that content changes.

| Bad id | Why it breaks | Stable replacement |
| --- | --- | --- |
| `2024-05-12-q3` | re-dating or re-ordering the paper changes it | `question-3` |
| `derivative-of-x-squared` | rewriting the stem orphans the id | `question-17` |
| `question-07-of-40` | inserting a question renumbers the tail | `question-7` |
| `hard-question` | difficulty is re-scored as the bank matures | `question-22` |

Numbered defaults are opaque on purpose: nothing a later edit touches.
A preferred slug (`chain-rule`) is acceptable only when the author treats it
as permanent, the same way a filename is.

## Hierarchical numbering

Ids are allocated at two levels with different scopes:

- **set id** - unique across the whole bank; names the stored file
  (`<root>/question_sets/<set-id>.json`);
- **question id** - unique only within its set.

The composition rule: a question is addressed by the pair
`(set id, question id)` - the set id locates the set, the question id locates
the entry inside it. Two sets may both contain `question-1` without
collision, because question numbering restarts within each set.

```text
set:      calculus-i
question: question-4        (inside calculus-i)
address:  calculus-i + question-4
```

## Case normalization

A preferred id passes through one deterministic rule (implemented in
`dq_questionbank.question_id`): lowercase, trim, collapse internal
whitespace runs to a single `-`, then drop every character outside
`[a-z0-9-_]`.

```text
"  Chain  Rule (v2) "  ->  "chain-rule-v2"
```

Step by step: trim and lowercase (`chain  rule (v2)`), collapse the double
space (`chain-rule-(v2)`), drop `(` and `)` (`chain-rule-v2`). The same input
always yields the same id, so normalization never forks one id into two
spellings.

## Stability across revisions

- An edited question **keeps its id**. Fix the stem, retag, re-score - the
  id is unchanged and every existing reference still resolves.
- A deleted id is **never reused**. `question-7` stays retired even after
  its question is gone.

Reuse breaks references silently. An export, a review note, or a colleague's
fork that still cites the retired `question-7` would attach to a brand-new
question with no error to notice, corrupting provenance invisibly.
Retirement is cheaper than repair.

## Interaction with allocation

Issue #88 added a pure allocation helper: same inputs, same output - no
timestamps, no hidden counters, no randomness. It collision-checks against
the caller-supplied existing ids and resolves conflicts with bounded
suffixes (`-2` through `-99`); exhausting the bound raises `ValueError`, so
allocation fails closed instead of inventing an unbounded id.

```python
from dq_questionbank.question_id import allocate_question_id, allocate_set_id

existing = {"question-1", "question-2"}

allocate_question_id(existing)                                # "question-3"
allocate_question_id(existing, preferred="Chain Rule")        # "chain-rule"
allocate_question_id({"chain-rule"}, preferred="chain-rule")  # "chain-rule-2"
```

The caller owns persistence: pass the ids already present in the set (or in
the bank, for sets) at insert time, store the returned id on the model, and
never re-allocate for an existing question. The end-to-end workflow is
introduced in the [README](../README.md).
