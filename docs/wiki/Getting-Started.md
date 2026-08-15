# Getting Started

Install the package, validate the synthetic sample, then convert it into a
reviewable format.

```bash
python -m venv .venv
python -m pip install -e ".[docx]"
dq validate examples/sample_questions.json
dq convert examples/sample_questions.json --output-format markdown -o questions.md
```

Run `dq serve` and open `http://127.0.0.1:8765` for the local browser
playground. It processes JSON locally and does not upload question content.

Continue with [Schema Reference](Schema-Reference.md) and
[Format Guide](Format-Guide.md).
