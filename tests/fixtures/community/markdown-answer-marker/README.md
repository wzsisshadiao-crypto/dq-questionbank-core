# Markdown answer-marker fixture

This original synthetic specimen places a line shaped like the Markdown
exporter's answer marker inside canonical stem text. It also includes a
pre-escaped marker to exercise reversible escaping.

Expected behavior:

- emit a backslash before a literal `**Answer:**` marker line;
- import that line back as stem text rather than a canonical answer;
- preserve an existing leading backslash by doubling it during export;
- leave the question without a canonical answer.

The fixture contains no source question content, private data, or external
assets. See `provenance.json` for redistribution status.
