# Review-first import cases

Version 0.7 ships five executable, synthetic cases behind one intake contract.
They demonstrate the handoff from source-specific extraction to canonical review;
they do not claim that one generic parser can understand every PDF or Word layout.

## Run the cases

```bash
dq intake cases
dq intake show coding-pdf
dq intake run coding-pdf -o workspace/coding-pdf
```

`run` writes three inspectable artifacts: the candidate session, the reviewed
session, and the exported canonical question set. It never writes to an
application question bank.

| Case | Route | Synthetic source | Boundary demonstrated |
|---|---|---|---|
| `manual-web` | Manual browser intake | Captured form JSON | Human entry still requires evidence and review |
| `web-ai` | Browser AI intake | DOCX draft | AI changes are digest-bound and field-allowlisted |
| `coding-word` | Regular AI Coding | DOCX | Source-specific extraction maps through the shared contract |
| `coding-pdf` | PDF AI Coding | Renderable PDF | Page locators remain attached to mapped fields |
| `coding-exam-omml` | Exam-specific AI Coding | DOCX with native OMML | Exam profile, native equation evidence, and rejection |

All materials are original synthetic fixtures. The cases contain no provider,
credential, private prompt, production database field, or real question-bank
content.

## The shared bundle seam

Each bundle contains a small declarative manifest plus source, records, evidence,
optional proposal, and review decisions:

```text
bundle.json
source.docx | source.pdf | form-submission.json
records.json
evidence.json
proposal.json       # optional
decisions.json      # required only by replayable installed cases
```

`bundle.json` maps extracted record paths to canonical question fields. Every
referenced file has a SHA-256 digest. Evidence binds a question field to the
declared source path, locator, excerpt, and excerpt digest. AI proposal entries
also carry a base digest, exact before value, bounded target field, and review
reason.

This makes extraction the only source-specific seam. A browser, coding agent, or
document adapter may produce `records.json` and `evidence.json`; all routes then
share mapping, diagnostics, validation, candidate state, review, and export.

## Adapt one case

Start from the case nearest to the source convention, retain the filenames or
update their references, and replace only synthetic source-specific extraction
data. Recompute each manifest digest after a referenced file changes.

```bash
dq intake prepare path/to/bundle -o candidate-session.json
dq intake review candidate-session.json --decisions decisions.json -o reviewed-session.json
dq intake export reviewed-session.json -o question-set.json
```

The prepare command reports unmapped source fields in candidate diagnostics.
This prevents new source data from disappearing merely because a mapping was not
updated. Review decisions are bound to each candidate digest; stale decisions
fail closed. Export is blocked until every candidate is explicitly accepted or
rejected, and rejected candidates are omitted.

## Rebuild the fixtures

The checked-in DOCX, OMML, PDF, JSON, digests, proposals, and decisions are
generated deterministically:

```bash
python -m pip install -e ".[docx,dev]"
python scripts/build_import_cases.py
git diff --exit-code
```

CI runs the same rebuild check. The public-tree audit accepts only the four exact
reviewed binary source paths and verifies their file signatures and size limits.
