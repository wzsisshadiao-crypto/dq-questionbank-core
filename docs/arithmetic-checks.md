# Conservative Arithmetic Checks

This document describes the conservative arithmetic consistency checks in
`dq_questionbank.math_consistency` (part of #97). They verify simple
numeric identities — bounded finite sums, direct arithmetic — WITHOUT
evaluating free variables. Anything clever, ambiguous, or fishy is skipped
with a stable reason. Findings are reports, never rewrites.

## Conservatism first

Every rule below must hold before any comparison runs; otherwise the input
is skipped, not guessed at:

- candidates come only from the LaTeX of `math` blocks in the stem; a
  single surrounding pair of `$...$`, `\(...\)`, or `\[...\]` is stripped;
- an expression is evaluable only when fully numeric — digits, `+`, `-`,
  `*`, `/`, `^`, parentheses, `.`, and whitespace. Any ASCII letter means
  a free variable; any other character (a macro, a brace) is unparseable;
- ellipsis sums such as `1 + 2 + \cdots + 100` are evaluated only when the
  listed terms form an exact arithmetic progression landing on the final
  term within `MAX_SUM_TERMS` (1000); `\sum` notation names a bound
  variable and is never expanded;
- evaluation uses a small hand-written recursive-descent parser over
  `^ * / + -` where `^` binds tightest and is right-associative; there is
  no `eval` and no new dependency;
- division by zero and any intermediate or final magnitude above
  `MAX_ABS_VALUE` (10^12) skip with their own reasons;
- the answer side is consulted only for a `text` answer whose value is a
  plain number or a fully-numeric string;
- each evaluable stem expression is compared with the answer independently;
  a difference beyond a `1e-9` relative tolerance becomes one finding.

## Skip reasons

`check_arithmetic(question)` returns an `ArithmeticCheckReport`; the
`skipped` tuple explains every refusal with one of seven closed reasons:

| Reason | When it is reported |
|---|---|
| `free-variables` | the expression contains an ASCII letter |
| `non-numeric-answer` | the answer is not a plain number or fully-numeric string |
| `division-by-zero` | a division by zero occurred while evaluating |
| `sum-terms-exceeded` | an ellipsis progression exceeds `MAX_SUM_TERMS` (1000) |
| `magnitude-exceeded` | any intermediate or final value exceeds 10^12 |
| `unparseable-expression` | the input falls outside the numeric grammar (macros, braces) |
| `no-numeric-expressions` | the stem has no math blocks with LaTeX |

Each skip carries a `locator` — `stem/blocks/2` for one stem math block,
`stem` for the whole stem, `answer` for the answer side — so a reviewer
can see exactly what was declined and why. Both `ArithmeticSkip` and the
report round-trip through `to_dict` / `from_dict`, and `from_dict`
rejects any reason outside the closed vocabulary above.

## Recipe

```python
from dq_questionbank import Answer, Content, ContentBlock, Question
from dq_questionbank.math_consistency import check_arithmetic

question = Question(
    "q-math-1",
    "short_answer",
    Content(
        [
            ContentBlock(type="math", latex="3+4*2"),
            ContentBlock(type="math", latex="x+1"),
        ]
    ),
    answer=Answer(kind="text", value="14"),
)

report = check_arithmetic(question)
report.findings[0].explanation
# "Arithmetic mismatch: the stem block computes 11 but the answer says 14."
[(skip.locator, skip.reason) for skip in report.skipped]
# [("stem/blocks/1", "free-variables")] — the x was never evaluated
```

The check is pure: it reads the question, evaluates what conservatism
allows, and returns findings and skips without touching the input.

## Fitting the quality vocabulary

A mismatch is one plain `QualityFinding` (see
[Revision-Bound Quality Findings](quality-findings.md)):

- `rule_id` is `arithmetic-mismatch` under ruleset `quality/1`;
- `target_field` points at the offending `stem.blocks[i]`;
- `input_fingerprints` covers both sides the rule actually read — the
  block and the `answer` — so `finding_state` stays meaningful and the
  finding goes stale exactly when either side changes;
- `severity` is `warning`, and the explanation cites both computed values.

Because the findings are ordinary `quality/1` findings, they serialize
with the standard `to_dict`, integrate with judgment via
`judge_finding`, and need no new frontend plumbing.
