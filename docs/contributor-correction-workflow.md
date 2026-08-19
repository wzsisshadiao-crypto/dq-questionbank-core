# Contributor Correction Workflow

This guide walks through a small, public correction contribution from the
first synthetic example to a reviewable pull request. It is intentionally
provider-neutral and uses only the public workspace and original English data.

## Public boundary

Contributors do not need the private application, the production question bank,
or an AI provider account. A correction contribution should be deterministic,
reviewable, and safe to run against a temporary local workspace.

The public Quality Center currently computes local findings and can open a
finding at its question and field in the Editor Center. The persisted,
revision-bound finding contract is a separate architecture task in Issue #6;
this guide does not introduce or imply that contract.

## A bounded example

Use one small rule rather than a general symbolic simplifier. For example, a
function-name rule may recognize these exact forms inside a math expression:

| Input | Proposed result | Decision |
| --- | --- | --- |
| `sin x + cos x` | `\\sin x + \\cos x` | Safe preview |
| `log(x)` | `\\log(x)` | Safe preview |
| `sinusoidal` | unchanged | Do not guess |

Give the rule a stable identifier such as `latex.function-name` and keep the
before/after values in a small fixture. The fixture should also cover an
ambiguous or malformed expression and prove that the original text is kept for
manual review.

## Where the change belongs

Start by locating the nearest public quality-check code and its tests. Keep the
following responsibilities separate:

1. **Rule logic:** recognize the bounded pattern and return a finding or a
   preview-only proposal.
2. **Fixture:** store original English input, expected result, rule ID, target
   field, and the expected decision in a small test fixture.
3. **Focused test:** prove safe, ambiguous, unchanged, and repeated-application
   behavior. A safe repair should be idempotent.
4. **Workspace handoff:** expose the finding with its question ID, field, and
   human-readable message so the existing Quality Center can open the relevant
   Editor Center section. Do not silently save a proposed repair.

If the public package does not yet have a reusable rule registry for the chosen
category, describe that missing extension point in the pull request instead of
adding hidden global state or copying private correction code.

## Local verification

Run the focused test first, then the repository checks:

```bash
python -m unittest discover -s tests -v
python -m ruff check src tests scripts
python scripts/audit_public_tree.py
python -m build
```

For a visual check, start the local workspace with `python run.py`, choose **Open
public case**, open **Quality Center**, run the checks, and use **Open in Editor**
on the synthetic finding. Confirm that the target field is visible, the source
text remains available, and no private or generated database is created.

## Pull request checklist

- Link the relevant issue, for example `Closes #17`.
- Explain the rule's intended scope and its manual-review boundary.
- Include only original synthetic fixtures and English technical text.
- List the focused test and the full local gate that you ran.
- Do not commit SQLite files, logs, credentials, provider configuration, private
  URLs, or real examination content.
- Keep the PR focused; a later rule or UI improvement can use a separate issue.
