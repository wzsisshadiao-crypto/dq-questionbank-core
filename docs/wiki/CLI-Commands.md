# CLI Commands

```bash
dq validate questions.json
dq import exam.docx -o questions.json
dq convert questions.json --output-format markdown -o questions.md
dq formats
dq serve --host 127.0.0.1 --port 8765
```

`validate` exits with `0` for valid input, `1` for validation errors, and `2`
for unreadable input. `import` writes canonical JSON. `convert` requires an
output format and target. `formats` lists built-in adapters; plugins remain
application-controlled and are never auto-loaded by the CLI.
