# Tricky LaTeX fragment

This original synthetic specimen contains a deliberately incomplete fraction
inside a balanced pair of inline math delimiters. It exercises the current
best-effort LaTeX importer without pretending to validate or repair arbitrary
LaTeX.

Expected behavior:

- import the single enumerate item as question `q1`;
- preserve the formula text `\frac{1}{x+1` exactly in a math block;
- leave correction or compilation to a later review step.

The fixture contains no source question content, private data, or external
assets. See `provenance.json` for redistribution status.
