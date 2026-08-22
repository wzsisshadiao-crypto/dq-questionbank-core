# LaTeX repair rule-set fixture

This original synthetic specimen pair backs the deterministic LaTeX repair
rule set that composes several bounded rules in one pass:

- before: `\left(  sin x   +   cos x  \right)`
- after: `\left(\sin x + \cos x\right)`

Applied rules, in order: `latex-bare-function-names` (`sin`/`cos` get a
backslash), `latex-delimiter-spacing` (whitespace directly inside the
`\left(`/`\right)` pair is dropped), and `latex-operator-spacing` (doubled
spaces around `+` collapse to one).

The same payload also pins two negative guarantees:

- `\text{a  +  b}` is preserved verbatim, because prose spacing inside
  `\text{...}` is intentional;
- the malformed `(x+1]` stays untouched and surfaces the
  `latex-mismatched-delimiters` manual-review finding instead of a repair,
  because the intended bracket cannot be guessed deterministically.

Every outcome keeps the original source visible until the repair is
accepted. The fixture contains no source question content, private data, or
external assets. See `provenance.json` for redistribution status.
