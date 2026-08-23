# OMML-to-LaTeX Import

The Word publishing path exports canonical LaTeX into native Word math.
`dq_questionbank.omml_import` is the import direction: it reads
`m:oMath` / `m:oMathPara` elements from a DOCX's `word/document.xml`
using only the standard library.

```python
from pathlib import Path

from dq_questionbank import read_docx_math

formulas = read_docx_math(Path("published.docx"))
for formula in formulas:
    print(formula.latex, formula.display, formula.unsupported)
```

Each `OmmlFormula` carries the LaTeX source, whether the formula was
display math (an `m:oMathPara` wrapper), and the constructs that had no
deterministic mapping.

## Covered constructs

- fractions (`m:f`) -> `\frac{num}{den}`
- sub/superscripts and sub+sup pairs -> `_{}`/`^{}`/both
- square and n-th roots (`m:rad`) -> `\sqrt{}`/`\sqrt[n]{}`
- delimiters (`m:d`) with custom begin/end characters -> `\left..\right`
- named functions (`m:func`) -> standard commands (`\sin`, `\ln`, ...)
  or `\operatorname{...}` for unknown names
- n-ary operators (`m:nary`: ∑, ∫, ∏, ...) with bounds
- plain runs, including unicode symbols

## Fail-closed behavior

Constructs with no deterministic LaTeX form are **never guessed**: their
text content is preserved in the LaTeX output and the construct name is
reported on `unsupported` (for example `bar`), so a caller can surface a
manual-review finding instead of accepting a silently wrong formula.

The synthetic demonstration fixture lives in `tests/fixtures/omml/`
(committed as base64 so the public tree stays text-auditable).
