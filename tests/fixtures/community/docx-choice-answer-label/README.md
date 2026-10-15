# DOCX choice-answer label fixture

This original synthetic fixture describes a small DOCX document using the
public field-label convention. The test builds the DOCX at runtime so every
source paragraph remains text-auditable in `fixture.json`.

The answer uses a JSON-style list:

```text
Answer: choices:["A", "B"]
```

Expected behavior:

- import the documented question ID, type, language, stem, and choices;
- normalize the quoted list members to choice IDs `A` and `B`;
- never retain the JSON quote characters in the canonical answer value.

The fixture contains no source question content, private data, or external
assets. See `provenance.json` for redistribution status.
