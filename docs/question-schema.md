# Question Schema

Schema version `1.0` defines a transport model, not a database schema.

## Design principles

- JSON is the normative serialization.
- Meaning is independent of database and UI layout.
- Content is an ordered list of typed blocks.
- Assets are references with optional integrity metadata.
- Composite questions recurse through `subquestions`.
- Experimental fields belong in `metadata` until standardized.
- Every serialized question declares its schema version.

## Main objects

### QuestionSet

A named collection with a language, description, metadata, and ordered questions.

### Question

Required fields are `schema_version`, `id`, `type`, `language`, and `stem`. Optional fields cover subject, choices, answer, solution, hints, assets, tags, normalized difficulty, source, taxonomy, subquestions, and metadata.

### Content

`Content.blocks` preserves order across:

- `text`
- `math` using LaTeX
- `image` using an `asset_id`
- `table` using a two-dimensional string array
- `code`
- `line_break`

### Answer

`kind` describes how to interpret `value`. Built-in validation understands `choice` and `choices`; other answer kinds remain serializable for domain-specific evaluators.

### Asset

An asset has an id, kind, URI, optional media type, optional SHA-256 digest, dimensions, and metadata. Local URIs must be relative and cannot traverse a parent directory. The core does not fetch remote assets.

## Versioning

The model uses `MAJOR.MINOR` schema versions independently from package semantic versions. Readers reject unsupported versions instead of silently changing meaning. During the package's `0.x` phase, a schema-breaking change requires a new schema version and migration documentation.

## Extensions

Use `metadata` with a namespaced key, for example:

```json
{
  "metadata": {
    "org.example.scoring": {
      "points": 2
    }
  }
}
```

Do not place secrets, absolute paths, provider credentials, or personal data in extension metadata.

