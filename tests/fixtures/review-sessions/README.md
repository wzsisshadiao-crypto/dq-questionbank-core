# Review-session contract fixtures

These original synthetic specimens back the public reviewable
import-candidate-session contract (`dq_questionbank.review_session`). All
documents are digest-bound sessions generated from the installed
`manual-web` synthetic case; they contain no private prompts, provider
wiring, source documents, or production schemas.

- `pending-session.json` — a freshly extracted session: every candidate is
  `pending`, the session retains the parser identity and source evidence,
  and the digest verifies.
- `reviewed-session.json` — after one explicit accept with a reviewed edit:
  the candidate decision is `accepted`, its payload digest is rebound, and
  its deterministic `revision` bumped from 1 to 2.
- `rejected-session.json` — after one explicit reject: the same base
  session with the candidate decision `rejected`; nothing was rewritten.
- `exported-questions.json` — the canonical question set exported from the
  reviewed session (accepted candidates only).

No candidate state implies persistence or AI approval: export returns a
`QuestionSet` value and never writes to an application store.
