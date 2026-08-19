# Word Publishing Envelope

This document defines a small, provider-neutral reference envelope for a future
local Word publishing bridge. It is a contract and fixture target, not an
implementation promise: the repository does not ship a Word macro, accept
credentials, or open a remote publishing service.

## Boundary

An envelope describes which canonical question revision a managed document
block represents and how a local authoring tool should refresh or reject that
block. The Word document remains owned by the authoring tool. A publisher must
not silently replace a block when its question revision has changed.

The reference service origin is loopback-only. A conforming implementation must
reject remote origins, implicit network fetches, and credentials in the
envelope. The synthetic fixture uses `http://127.0.0.1:8766` only as an example
origin; it is not a running endpoint.

## Envelope shape

The minimum fields are:

| Field | Meaning |
| --- | --- |
| `envelope_version` | Version of this contract, independent of the question schema. |
| `document_id` | Stable identifier for the authoring document. |
| `mode` | `compose` for visible reference borders or `final` for output rendering. |
| `service_origin` | Explicit loopback origin; never a public or remote URL. |
| `blocks` | Ordered managed question blocks. |
| `refresh` | Explicit behavior for refresh, missing questions, and stale revisions. |
| `rollback` | Scope and behavior when a refresh fails. |
| `security` | Allowed origins and credential policy. |

Each block contains a stable `block_id`, `question_id`, `question_fingerprint`,
field roles, and display hints. The fingerprint is a deterministic SHA-256
identifier for the canonical revision the block was rendered from; it is not a
secret and must not be used as authorization.

## Refresh and rollback

- Refresh is explicit and ordered by the envelope's `blocks` list.
- A missing question or fingerprint mismatch produces a stale result; it does
  not silently substitute another question.
- A failed refresh restores the previous content of the affected block. A
  conforming implementation may roll back one block or the whole document, but
  the chosen scope must be declared before work starts.
- `compose` may show borders and diagnostic labels. `final` must omit those
  authoring affordances while retaining the same stable question identity.
- Native Word math, images, tables, choices, answers, analysis, and solutions
  are rendering roles. The envelope does not prescribe a macro implementation
  or claim that every role is supported today.

## Security and compatibility

Only loopback origins explicitly listed in `security.allowed_origins` are
permitted. `security.remote_origins` must be empty and `security.credentials`
must be `never` for the reference envelope. A future bridge must fail closed on
an invalid origin, unknown envelope version, duplicate block id, missing
fingerprint, or unsupported refresh/rollback policy.

The fixture at
`tests/fixtures/word-publishing/synthetic-envelope.json` is deliberately small
and contains no real question bank content. Its test checks shape, deterministic
serialization, loopback restrictions, and stale-revision behavior without
starting a service or writing a document.
