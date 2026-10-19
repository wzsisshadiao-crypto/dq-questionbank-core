# Markdown question-header fixture

This original synthetic specimen places a line shaped like the Markdown
exporter's question header inside canonical stem text. It also includes a
pre-escaped header to exercise reversible escaping.

Expected behavior:

- emit a backslash before a literal generated question-header line;
- import that line back as stem text instead of a second question;
- preserve an existing leading backslash by doubling it during export;
- leave the question set with exactly one canonical question.

The fixture contains no source question content, private data, or external
assets. See `provenance.json` for redistribution status.
