# Welcome to the DQ QuestionBank Core Wiki

DQ QuestionBank Core is a local-first, open-source foundation for
structured educational questions: a database-neutral Python library, a CLI,
and a visual workspace that runs entirely on your machine. Apache 2.0.

**New here?** [Getting Started](Getting-Started.md) takes you from zero to
the visual workspace in three steps (double-click `start.bat`, or
`pip install dq-questionbank-core` + `dq-local`).

## Understand the system

- [Architecture](Architecture.md) - the complete guide: layers, module map,
  data flow, hard boundaries, extension points
- [Mechanisms](Mechanisms.md) - how each engine works: schema versioning,
  atomic storage, review-first intake, quality gates, the three LaTeX
  engines, the Word publishing envelope, PDF/coding-agent gates,
  determinism, security

## Reference

- [Getting Started](Getting-Started.md)
- [Installation](Installation.md)
- [Schema Reference](Schema-Reference.md)
- [Format Guide](Format-Guide.md)
- [CLI Commands](CLI-Commands.md)
- [Plugin Development](Plugin-Development.md)
- [FAQ](FAQ.md)

## About this Wiki

The repository directory `docs/wiki/` is the only editable source for these
pages; the live Wiki is a deterministic export. Use
`python scripts/wiki_sync.py check`, `export`, or `sync` rather than
editing the rendered target directly.
