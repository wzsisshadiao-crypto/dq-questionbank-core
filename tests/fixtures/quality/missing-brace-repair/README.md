# Missing-brace repair fixture

This original synthetic specimen pair backs the first deterministic LaTeX
repair rule (`latex-missing-closing-brace`). The before payload contains one
structurally complex, nested-but-otherwise-intact formula that is missing
exactly one closing brace:

- before: `\frac{\sqrt{3}}{x+1`
- after: `\frac{\sqrt{3}}{x+1}`

Expected behavior:

- applying `repair_latex_braces` to the before math block yields the after
  payload exactly, in one step;
- the original source stays visible on the outcome until the repair is
  accepted;
- ambiguous damage (missing opening brace, multiple breaks, trailing escape)
  is never rewritten and is reported as a finding instead.

The fixture contains no source question content, private data, or external
assets. See `provenance.json` for redistribution status.
