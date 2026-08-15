# Schema Reference

The canonical interchange format is the versioned JSON Schema at
`schema/question-set.schema.json`. A question set has an ID, title, language,
and ordered questions. Every question declares a type, language, and content
blocks for its stem.

The model supports text, LaTeX math, image references, tables, code, and line
breaks. Asset paths must be relative and cannot traverse parent directories;
remote assets are represented but never fetched implicitly.

Read the full [question schema](../question-schema.md) before introducing a
schema version or a new required field.
