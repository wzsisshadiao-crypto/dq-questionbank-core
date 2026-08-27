# Installation

DQ QuestionBank Core supports Python 3.10, 3.11, and 3.12. The core
library and the visual workspace are stdlib-only; the `docx` extra adds
DOCX import/export, and `dev` adds the test/lint/build tooling.

## From PyPI (library + CLI + visual launcher)

```bash
python -m pip install dq-questionbank-core
dq --version
dq-local            # visual workspace on http://127.0.0.1:8766
```

## From source (no install needed)

```bash
git clone https://github.com/wzsisshadiao-crypto/dq-questionbank-core
cd dq-questionbank-core
# Windows: double-click start.bat    macOS/Linux: sh start.sh
python run.py        # same thing from a terminal
```

The launcher path needs no pip install at all - the visual workspace runs
straight from the checkout.

## For development

```bash
python -m pip install -e ".[docx,dev]"
python -m unittest discover -s tests
python -m ruff check src tests scripts run.py
```

See the repository [compatibility policy](../compatibility.md) for version
guarantees and [Getting Started](Getting-Started.md) for the first session.
