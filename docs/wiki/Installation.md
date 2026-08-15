# Installation

DQ QuestionBank Core supports Python 3.10, 3.11, and 3.12.

```bash
git clone https://github.com/wzsisshadiao-crypto/dq-questionbank-core
cd dq-questionbank-core
python -m pip install -e ".[docx,dev]"
dq --version
```

The `docx` extra installs DOCX import/export support. The `dev` extra installs
the test, lint, build, and schema-validation tools. See the repository
[compatibility policy](../compatibility.md) for version guarantees.
