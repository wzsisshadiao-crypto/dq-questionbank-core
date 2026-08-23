# Graded LaTeX Normalization

This document describes the graded LaTeX normalization engine in
`dq_questionbank.latex_normalize` (part of #94). Mechanical noise — double
spaces, trailing blanks, padded inline delimiters — wastes review time,
and safe cleanups can apply automatically. Risky rewrites (merging
subscripts, inserting explicit multiplication) are plausible but never
certain, so they must never silently edit a formula.

## The grade is the contract

A `NormalizationRule` carries five parts: `id`, `grade`, `explanation`,
`match`, and `apply`. The grade decides what the engine may do with it:

- `autoFixable` — the rule applies mechanically inside `normalize_latex`;
- `reviewReason` — the rule only ever contributes a proposal (rule id,
  grade, reason, current source, proposed text).

This is a structural guarantee, not a convention: the engine's code path
for `reviewReason` rules never assigns to the result, so their `apply`
return value cannot reach the output no matter what a rule does. An
unknown grade raises `ValueError` before anything runs.

`normalize_latex(source)` returns a `NormalizedLatex`:

- `source` is always the untouched original; `result` equals it when
  nothing auto-applies;
- `applied_rules` lists the autoFixable rule ids that actually changed
  the text, in registry order — a rule that matches but changes nothing
  is not recorded, which keeps every built-in cleanup idempotent;
- `proposals` holds one entry per matching reviewReason rule, each
  evaluated against the **original** source.

## Built-in rules

`BUILT_IN_RULES` runs in this fixed order:

| Rule id | Grade | What it does |
|---|---|---|
| `collapse-space-runs` | `autoFixable` | Collapse runs of two or more spaces to one |
| `strip-trailing-space` | `autoFixable` | Remove trailing blank spaces |
| `normalize-inline-dollar-spacing` | `autoFixable` | Drop padding spaces inside single-dollar inline math |
| `double-subscript-merge` | `reviewReason` | Two consecutive subscript groups may be one merged subscript |
| `implicit-multiplication-digit-letter` | `reviewReason` | A digit glued to a letter may mean explicit multiplication |

The space rules rewrite only outside protected regions —
`\text{...}`, `\textrm{...}`, `\mathrm{...}`, and `\operatorname{...}`
spans stay verbatim, mirroring the preserved-prose guarantee of the
repair rules. `NormalizationRule.from_dict` resolves only built-in ids
and rejects a grade that disagrees with the registry.

## Recipe: one combined run

```python
from dq_questionbank.latex_normalize import normalize_latex

outcome = normalize_latex("x_{a}_{b}  ")

outcome.source          # "x_{a}_{b}  "  (untouched original)
outcome.result          # "x_{a}_{b}"    (auto-applied)
outcome.applied_rules   # ("collapse-space-runs", "strip-trailing-space")

outcome.proposals
# ({
#     "rule_id": "double-subscript-merge",
#     "grade": "reviewReason",
#     "reason": "Two consecutive subscript groups may be one merged subscript.",
#     "current": "x_{a}_{b}  ",
#     "proposed": "x_{ab}  ",
# },)
```

Two things are worth reading off this run. First, the risky merge was
**not** applied: `result` keeps both subscript groups, and the proposal
alone shows what merging would look like. Second, the proposal's
`current` / `proposed` pair always cites the original source — proposals
never see the auto-applied cleanups, so the reviewer compares like with
like. Re-running the engine on `outcome.result` applies nothing further
and returns the same text (idempotency), and `NormalizedLatex`
round-trips through `to_dict` / `from_dict`.

## Relationship to the repair rules

`src/dq_questionbank/latex_repair.py` (see
[Correction Rule Workflow](correction-rule-workflow.md)) fixes *broken*
sources — missing braces, bare function names, delimiter and operator
spacing — fail-closed, with ambiguous input routed to manual review.
Normalization targets a different stage: mechanically noisy but valid
input, cleaned before or alongside repair. Both share the same
discipline: the original always travels next to the proposal, every
applied rule id is reported, and nothing risky ever edits a formula
without an explicit human decision.
