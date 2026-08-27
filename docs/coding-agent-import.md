# Coding-Agent Import Contract

This guide documents the work-file contract a coding agent follows when it
imports questions with workspace access: the agent reads evidence, edits a
JSON work file, and the deterministic pipeline — never the agent — owns
identity, evidence binding, and publication. The contract lives in
`dq_questionbank.coding_agent_workfile`.

## The loop

```text
transcribe each question
    pending_transcription -> transcribed | needs_review
run deterministic repairs          (latex_compat, latex_repair, ...)
validate the work file             validate_work_file
stage one qNN.json per question
scan the staged directory          pdf_postflight.scan_candidate_dir
register for human review          (out of scope here)
```

A question may bounce `transcribed -> needs_review -> transcribed` as the
agent resolves doubts against the evidence, but it can never go backwards
to `pending_transcription`: re-dispatch belongs to the pipeline owner.

## The work file

One JSON object, one stable schema tag:

```json
{
  "schema": "coding-agent-workfile/v1",
  "questions": [
    {
      "question_number": "1.1",
      "body": "Compute $\\int_0^1 x\\,dx$.",
      "answer": "$\\frac{1}{2}$",
      "explanation": "Fundamental theorem of calculus.",
      "work_status": "transcribed"
    }
  ]
}
```

| Rule | Why |
|---|---|
| `question_number` present and unique | duplicates break the dispatch queue |
| `work_status` one of `pending_transcription`, `transcribed`, `needs_review` | the loop has exactly these states |
| `body`/`answer` non-empty once `transcribed` | a finished question is finished |
| `work_note` required for `needs_review` | a doubt without a reason cannot be triaged |
| pipeline-owned fields forbidden | see below |

## Forbidden fields

`schema`, `job_id`, `workset_id`, `run_id`, `question_id`, `evidence_dir`,
`evidence_pages`, `evidence_sha256`, `complete`, `cards` are owned by the
dispatcher and the finalize stage. The agent file must not carry them:
overriding identity or evidence from the transcription side is how
mis-bound questions enter a bank silently. `validate_work_file` reports
each occurrence.

## Using the module

```python
from dq_questionbank.coding_agent_workfile import (
    WORK_STATUS_TRANSCRIBED,
    read_work_file,
    transition_work_status,
    validate_work_file,
    write_work_file,
)

payload = read_work_file("cards.json")
findings = validate_work_file(payload)
assert not findings, findings
payload = transition_work_status(payload, "1.1", WORK_STATUS_TRANSCRIBED)
write_work_file("cards.json", payload)   # atomic: temp file + os.replace
```

`transition_work_status` never mutates its input and rejects transitions
outside the loop; entering `transcribed` clears `work_note` because the
doubt it described is resolved. `read_work_file` tolerates a UTF-8 BOM
added by editors.

## Downstream gates

- **Postflight.** After staging one `qNN.json` per question,
  [`pdf_postflight.scan_candidate_dir`](pdf-toolchain.md) verifies
  continuity, required identity fields, and content hashes before
  registration.
- **Paper metadata.** Whole volumes must agree on subject, question type,
  source, and grade: `dq_questionbank.pdf_metadata` fails closed on the
  first diverging row.
- **Job identity.** `dq_questionbank.pdf_identity.job_matches_tag` decides
  whether a runtime job id belongs to a canonical paper tag.

## LaTeX repairs the agent may rely on

`dq_questionbank.latex_compat` ships the two deterministic repairs that
PDF transcription most often needs, both pure functions with stats:

- `restore_degraded_relation_pairs` — the `$A$，$\quad B$` degradation
  footprint is restored only when both sides are relation expressions;
  coordinates, intervals, and function arguments stay untouched.
- `normalize_integral_differentials` — bare `dx`/`d\theta` inside integral
  spans becomes `\mathrm{d}`; non-integral math is never rewritten.

Anything not covered by a deterministic rule stays in `work_note` and goes
to human review — that is the point of the contract.
