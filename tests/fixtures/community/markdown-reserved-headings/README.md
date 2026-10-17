# Markdown reserved-heading fixture

This original synthetic specimen places the Markdown exporter's structural
section headings inside canonical stem text. It also includes a pre-escaped
heading to exercise reversible escaping.

Expected behavior:

- emit a backslash before literal `### Choices`, `### Solution`, and
  `### Hint N` lines;
- import those lines back as stem text rather than structural sections;
- preserve an existing leading backslash by doubling it during export;
- leave the question without a canonical solution or hints.

The fixture contains no source question content, private data, or external
assets. See `provenance.json` for redistribution status.
