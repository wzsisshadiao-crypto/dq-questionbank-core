# Nested LaTeX enumerate fixture

This original synthetic specimen contains two outer question items. The first
question includes a nested `enumerate` list as part of its stem. It exercises
the best-effort LaTeX fallback importer without asking it to interpret the
nested list as canonical answer choices.

Expected behavior:

- import only the two outer items as questions `q1` and `q2`;
- preserve the nested environment inside the first question's text;
- never promote the nested `Four` and `Five` items to standalone questions.

The fixture contains no source question content, private data, or external
assets. See `provenance.json` for redistribution status.
