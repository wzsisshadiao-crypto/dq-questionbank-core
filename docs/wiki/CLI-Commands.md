# CLI Commands

```bash
dq validate questions.json
dq import exam.docx -o questions.json
dq intake cases
dq intake run coding-pdf -o workspace/coding-pdf
dq intake prepare path/to/bundle -o candidate-session.json
dq intake review candidate-session.json --decisions decisions.json -o reviewed-session.json
dq intake export reviewed-session.json -o question-set.json
dq word-publish question-set.json -o paper.docx --envelope paper.envelope.json
dq word-macro -o DQWordPublishing.bas
dq word-serve question-set.json --host 127.0.0.1 --port 8766
dq convert questions.json --output-format markdown -o questions.md
dq formats
dq serve --host 127.0.0.1 --port 8765
```

`validate` exits with `0` for valid input, `1` for validation errors, and `2`
for unreadable input. `import` writes canonical JSON. `convert` requires an
output format and target. `formats` lists built-in adapters; plugins remain
application-controlled and are never auto-loaded by the CLI.

`intake run` replays an installed synthetic case. `prepare`, `review`, and
`export` expose the same digest-bound states for custom bundles. No intake
command persists a candidate to an application question bank.

`word-publish` creates managed Word content controls bound to canonical question
fingerprints. `word-macro` exports the matching VBA template. `word-serve`
starts a credential-free loopback bridge for explicit insert and refresh
requests; it does not import or persist questions.
