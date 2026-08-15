"""Explicit discovery for third-party format plugins.

Plugins are discovered only when an application calls :func:`discover_plugins`.
The default registry deliberately remains limited to built-in adapters.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points
from typing import Callable, Iterable

from .exceptions import PluginDiscoveryError
from .registry import FormatRegistry


PLUGIN_ENTRY_POINT_GROUP = "dq_questionbank.plugins"
PluginRegistrar = Callable[[FormatRegistry], None]


def _plugin_entries(group: str) -> tuple[EntryPoint, ...]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        selected: Iterable[EntryPoint] = discovered.select(group=group)
    else:  # pragma: no cover - compatibility with Python 3.9 metadata backports
        selected = discovered.get(group, ())
    entries = tuple(sorted(selected, key=lambda entry: (entry.name, entry.value)))
    names = [entry.name for entry in entries]
    if len(names) != len(set(names)):
        raise PluginDiscoveryError(f"Duplicate plugin entry point names in group {group!r}")
    return entries


def available_plugins(*, group: str = PLUGIN_ENTRY_POINT_GROUP) -> tuple[str, ...]:
    """Return installed plugin names in deterministic order without loading them."""
    return tuple(entry.name for entry in _plugin_entries(group))


def discover_plugins(
    registry: FormatRegistry, *, group: str = PLUGIN_ENTRY_POINT_GROUP
) -> tuple[str, ...]:
    """Load and invoke registered plugin functions for ``registry``.

    Each entry point in ``dq_questionbank.plugins`` must resolve to a callable
    with the signature ``register(registry: FormatRegistry) -> None``. Discovery
    is opt-in because loading an installed package executes third-party code.
    """
    if not isinstance(registry, FormatRegistry):
        raise TypeError(f"discover_plugins requires a FormatRegistry, got {type(registry).__name__}")

    loaded: list[str] = []
    for entry in _plugin_entries(group):
        try:
            registrar = entry.load()
        except Exception as exc:
            raise PluginDiscoveryError(f"Could not load plugin {entry.name!r}") from exc
        if not callable(registrar):
            raise PluginDiscoveryError(f"Plugin {entry.name!r} is not a callable registrar")
        try:
            registrar(registry)
        except Exception as exc:
            raise PluginDiscoveryError(f"Plugin {entry.name!r} failed during registration") from exc
        loaded.append(entry.name)
    return tuple(loaded)
