# Plugin Development

The core exposes four protocols:

- `QuestionImporter`
- `QuestionExporter`
- `StorageAdapter`
- `AIProvider`

Create a caller-owned `FormatRegistry` and register format instances explicitly. Explicit registration keeps import behavior auditable and avoids executing unknown package entry points in `0.1`.

Private adapters should live in a separate repository. They may depend on the public core; the public core must never depend on them.

An AI adapter should receive an already constructed `QuestionSet`, document what data leaves the machine, avoid logging raw questions by default, and return a new or intentionally modified model. Credentials belong in environment-backed private configuration, never in canonical metadata.

