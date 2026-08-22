# Word Publishing

DQ QuestionBank Core ships a provider-neutral Word publishing workflow. It
turns reviewed canonical questions into managed Word content controls and lets
the bundled VBA client insert or explicitly refresh those blocks through a
loopback-only bridge.

This is a clean public implementation of the generic workflow. It does not
contain a production database adapter, private question data, provider prompts,
credentials, or deployment configuration. The bridge reads the canonical JSON
file selected by the user and never persists candidate questions.

## Quick start

Install DOCX support, then export a managed document and its envelope:

```bash
python -m pip install "dq-questionbank-core[docx]"
dq word-publish reviewed-questions.json -o paper.docx --envelope paper.envelope.json
dq word-macro -o DQWordPublishing.bas
dq word-serve reviewed-questions.json --port 8766
```

In desktop Word on Windows, import `DQWordPublishing.bas` in the VBA editor.
The public commands are:

| Macro | Behavior |
| --- | --- |
| `DQ_InsertReferenceBlock` | Resolve a question id through the local bridge, insert its current fingerprint, and render a managed block. |
| `DQ_RefreshCurrentBlock` | Refresh the block containing the cursor. |
| `DQ_RefreshAllBlocks` | Refresh managed blocks in Word document order. |
| `DQ_ShowComposeBlocks` | Show content-control borders while authoring. |
| `DQ_RenderFinal` | Refresh in final mode, then hide managed-block borders. |

The `.bas` file is an auditable template, not a signed Office add-in. Test it
against the Word version and macro policy used by your organization. Python
package and Open XML behavior is covered in CI; interactive Word execution is a
Windows integration check and is not run on Linux CI workers.

## Envelope contract

The current envelope version is `0.2`; the bridge also accepts the `0.1`
contract published in v0.7.0. The minimum fields are:

| Field | Meaning |
| --- | --- |
| `envelope_version` | Publishing contract version, independent of the question schema. |
| `document_id` | Stable authoring-document identifier. |
| `mode` | `compose` for authoring affordances or `final` for output rendering. |
| `service_origin` | Explicit HTTP loopback origin. |
| `blocks` | Ordered managed question blocks. |
| `refresh` | Explicit missing-question and revision-mismatch behavior. |
| `rollback` | Declared rollback scope and failure behavior. |
| `security` | Allowed origins and credential policy. |

Each block has a stable `block_id`, `question_id`, SHA-256
`question_fingerprint`, ordered rendering `roles`, and `display` hints. The
fingerprint covers deterministic canonical question JSON. It identifies a
revision; it is not authorization.

`build_envelope()`, `validate_envelope()`, and `question_fingerprint()` are the
normative Python implementation. `export_word_publishing()` writes rich-text
`w:sdt` controls tagged as:

```text
dqwb:<block-id>|<question-id>|sha256:<canonical-question-digest>
```

`extract_managed_blocks()` reads these markers without executing macros or
embedded document content.

## Refresh and rollback rules

- Refresh is user-triggered and preserves envelope or Word document order.
- A missing question produces `stale` with reason `missing-question`.
- A fingerprint mismatch produces `stale` with reason `revision-mismatch`.
- A stale block is never silently replaced with another revision.
- Rendering or bridge failure restores the previous content of that one block.
- A failure in one block does not rewrite unrelated blocks.
- `compose` shows authoring identity and permits visible borders.
- `final` omits the compose label and hides borders after every refresh succeeds.

The renderer covers stem, choices, answer, analysis metadata, and solution
roles. Canonical text, math, images, and tables remain represented by the
question model; the managed DOCX format is deliberately inspectable and leaves
the document editable in Word. Native OMML coverage varies by input and Word
version, so unsupported formulas retain readable canonical math text instead
of executing a conversion service.

## Bridge security

`WordPublishingBridge` accepts only `127.0.0.1`, `localhost`, or `::1`. The
envelope must declare exactly one matching loopback origin, an empty
`remote_origins` array, and `credentials: never`. Unknown versions, duplicate
block ids, missing fingerprints, remote origins, credentials, and unsupported
refresh or rollback policies fail closed.

The bridge exposes only:

| Endpoint | Purpose |
| --- | --- |
| `GET /status` | Protocol and credential-policy health check. |
| `POST /v1/insert` | Resolve one reviewed question and return its managed block. |
| `POST /v1/refresh` | Refresh ordered, fingerprint-bound blocks. |

It has no database endpoint, remote fetch path, credential header, import
execution path, or persistence operation. Mutating requests must carry the
versioned `X-DQ-Word-Protocol` header and are capped at 8 MiB; browser CORS is
not enabled.

## Compatibility and tests

The synthetic `0.1` fixture remains at
`tests/fixtures/word-publishing/synthetic-envelope.json`. Tests additionally
cover current envelope construction, remote-origin and duplicate rejection,
ordered refresh, stale retention, compose/final output, loopback HTTP behavior,
single-block rollback semantics, deterministic Word XML, managed content
controls, and static VBA safety properties.

Legal synthetic Word specimens and Windows/Word compatibility reports are
collected in [Issue #48](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/issues/48).
