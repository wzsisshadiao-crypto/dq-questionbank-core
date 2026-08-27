# LaTeX Discipline: One Gate, Detect-Count-Repair, and Locked Cases

How the project keeps imported LaTeX correct without a human eyeballing
every formula. Three practices, one per section.

## 1. One gate: correction panel == quality scan

There are not two notions of "wrong LaTeX". The deterministic detector is
the single authority, and every surface reads it:

- the review/correction UI lists findings from the same detector the
  quality scan runs (`quality_findings`, `latex_regression` faults);
- a finding carries the exact question and field it refers to, so the
  editor opens on the right spot;
- after a save, the scan re-runs and findings whose field fingerprint
  changed disappear; untouched ones survive. No finding is ever dismissed
  by hand-waving - only by changing the content it points at.

Consequence: fixing in the panel and re-scanning the bank can never
disagree, because they are the same code.

## 2. Detect - count - repair in one assertion

A repair rule is only well-defined when all three legs are pinned
together. `dq_questionbank.latex_compat` repairs report their counts in a
stats dictionary, and `dq_questionbank.latex_regression` cases assert
them alongside the text:

```json
{
  "name": "three-column-chain-rejoined-in-pairs",
  "text": "$a=1$，$\\quad b=2$，$\\qquad c=3$",
  "transform": "restore_degraded_relation_pairs",
  "expect_fix_count": 2,
  "expect_equals": "$a=1$，$b=2$，$c=3$",
  "expect_no_faults_after": true
}
```

- **detect** - `expect_issue_types` pins what the recognizer finds
  (double superscript/subscript, malformed `\frac`, ...);
- **count** - `expect_fix_count` pins how many fixes applied;
- **repair** - `expect_equals`/`expect_contains`/`expect_not_contains`
  pin the output text, and `expect_no_faults_after` guarantees the repair
  never introduces a structural fault.

## 3. Special cases are locked, not remembered

Hard-won edge cases go into the checked-in case file
(`src/dq_questionbank/data/latex_regression_cases.json`) and become
executable memory:

- coordinate pairs `$(x,y)$，$\quad (u,v)$` and intervals **must not**
  merge (fix count 0, text unchanged);
- a three-column relation chain **must** rejoin pair by pair (count 2);
- `dy/dx` stays italic outside integrals; only integral differentials go
  upright.

Run them anywhere:

```bash
python -m dq_questionbank.latex_regression
# cases=9 failed=0
```

### The change ritual

Before touching any LaTeX rule:

1. add (or confirm) a case that documents today's behaviour;
2. run the lock - all cases PASS;
3. make the change;
4. run again. An **intentional** behaviour change shows up as a named case
   failure; update that case in the same PR so reviewers see exactly which
   pinned behaviours moved. An **unintentional** change is a bug you just
   caught before merge.

## Reading map

- graded normalization (autoFixable vs reviewReason):
  [latex-normalization.md](latex-normalization.md)
- broken-source repair: [correction-rule-workflow.md](correction-rule-workflow.md)
- PDF-transcription compatibility repairs: [coding-agent-import.md](coding-agent-import.md)
- arithmetic-level checks: [arithmetic-checks.md](arithmetic-checks.md)
