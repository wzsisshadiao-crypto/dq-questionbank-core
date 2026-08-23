# OMML import fixtures

This original synthetic specimen backs the OMML-to-LaTeX import adapter
(`dq_questionbank.omml_import`). The DOCX is generated deterministically
with python-docx and injected OMML XML covering:

- an inline fraction and an inline sub+superscript pair;
- a square root and an n-th root;
- display formulas through `m:oMathPara`: a bounded sum and a named
  function inside delimiters;
- one deliberately unsupported construct (`m:bar`) to prove the
  preserved-text-plus-finding path.

Because the repository tree is text-auditable, the DOCX is committed
base64-encoded inside `omml-fixture.json` together with the expected
LaTeX output; `tests/test_omml_import.py` decodes it, writes it to a
temporary file, and imports it. See `provenance.json` for redistribution
status.
