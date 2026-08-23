# Plugin Development

The core exposes four protocols. Two are fully implemented; two are extension points.

## Implemented (built-in)

- `QuestionImporter` — JSON, Markdown, LaTeX, DOCX
- `QuestionExporter` — JSON, Markdown, LaTeX, DOCX

## Storage and AI extension points

`AIProvider` remains a protocol-only hook for private downstream projects.
`StorageAdapter` has a small local filesystem reference implementation; database,
cloud, and application-specific storage remain downstream integration work.

### StorageAdapter

```python
class StorageAdapter(Protocol):
    def save(self, question_set: QuestionSet) -> None: ...
    def load(self, question_set_id: str) -> QuestionSet: ...
```

Use for PostgreSQL, SQLite, S3, or any other backend. The open-source core never
calls this protocol automatically. Private projects import it, implement it, and
wire it into their own CLI or web servers. For a safe local JSON example, see
[Reference Filesystem Storage](filesystem-storage.md).

### AIProvider

```python
class AIProvider(Protocol):
    def enrich(self, question_set: QuestionSet, **options: Any) -> QuestionSet: ...
```

Intended for private AI enrichment: tag suggestions, difficulty estimation,
answer generation, translation. Credentials must live in environment variables or
a private configuration file, never in canonical question metadata.

## Registering custom importers/exporters

```python
from dq_questionbank import FormatRegistry

registry = FormatRegistry()
registry.register_importer(MyCustomImporter())
registry.register_exporter(MyCustomExporter())

question_set = registry.importer("my-format").load(source_path)
registry.exporter("json").dump(question_set, output_path)
```

Since v0.2.0, `register_importer` and `register_exporter` enforce the protocol
at registration time with `isinstance` checks. Passing a non-conforming object
raises `TypeError`.

## Registration and discovery are explicit

Create a caller-owned `FormatRegistry` and register format instances explicitly.
Explicit registration keeps import behavior auditable and avoids executing unknown
package entry points.
For reusable public plugins, publish one registrar under the stable
`dq_questionbank.plugins` entry-point group:

```toml
[project.entry-points."dq_questionbank.plugins"]
my_format = "example_plugin:register"
```

The registrar receives a caller-owned registry and uses the same protocol
checks as built-in registration:

```python
from dq_questionbank.plugins import discover_plugins
from dq_questionbank.registry import default_registry


def register(registry):
    registry.register_importer(MyCustomImporter())
    registry.register_exporter(MyCustomExporter())


registry = default_registry()
discover_plugins(registry)
```

`default_registry()` never discovers plugins. Discovery is an explicit
application decision because loading an installed package executes its code.
`available_plugins()` lists entry-point names without loading them; malformed,
duplicate, or failing plugins raise `PluginDiscoveryError`.

## A safe end-to-end example

[`examples/plugin_discovery_demo.py`](../examples/plugin_discovery_demo.py)
walks the whole discovery contract without installing anything or loading
unknown code. Run it locally from a repository clone:

```bash
python examples/plugin_discovery_demo.py
```

Expected output in a clean environment (no plugins installed):

```text
entry-point group: dq_questionbank.plugins
installed plugins (listing only, nothing loaded): 0
listing is read-only; pass --opt-in-load to run discover_plugins()
```

The default run only calls `available_plugins()`, which reads distribution
metadata and never imports plugin code. Passing `--opt-in-load` is the one
moment third-party code runs — it calls `discover_plugins()` against a fresh
registry, the same opt-in step an application takes deliberately:

```bash
python examples/plugin_discovery_demo.py --opt-in-load
```

With plugins installed, the listing shows their entry-point names and the
opt-in run reports which registrars were invoked. The example uses only
public interfaces, executes no repository code beyond itself, and fetches
nothing; a focused test in `tests/test_plugins.py` pins its output.

## Private adapters

Private adapters should live in a separate repository. They may depend on the
public core; the public core must never depend on them.

An AI adapter should receive an already constructed `QuestionSet`, document what
data leaves the machine, avoid logging raw questions by default, and return a new
or intentionally modified model.
