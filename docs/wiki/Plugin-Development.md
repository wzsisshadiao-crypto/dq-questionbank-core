# Plugin Development

Third-party format plugins use the `dq_questionbank.plugins` entry-point
group. Each entry point resolves to a registrar accepting a `FormatRegistry`.

```toml
[project.entry-points."dq_questionbank.plugins"]
my_format = "example_plugin:register"
```

```python
from dq_questionbank.plugins import discover_plugins
from dq_questionbank.registry import default_registry

registry = default_registry()
discover_plugins(registry)
```

Discovery is intentionally explicit. Loading an installed plugin executes
third-party code, so `default_registry()` only contains built-in adapters.
Registrars use the normal registry checks for importer and exporter protocols.

See [plugin development](../plugin-development.md) for the full contract and
private-adapter boundary.
