# Markdown indented-choice fixture

This original synthetic specimen contains a single-choice question whose list
items use three leading spaces, which remains valid Markdown list syntax. It
exercises the best-effort Markdown importer without relying on private or
externally sourced question content.

Expected behavior:

- import all three labeled items as canonical choices;
- preserve their IDs and visible text;
- retain `B` as the canonical answer.

Four or more leading spaces are intentionally outside this fixture's supported
choice syntax because Markdown can interpret them as an indented code block.
See `provenance.json` for redistribution status.
