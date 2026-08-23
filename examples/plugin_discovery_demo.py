"""A safe, self-contained plugin-discovery walkthrough.

This example demonstrates the public discovery API end to end without
installing anything, loading unknown code, or fetching remote packages:

1. The default run only *lists* installed plugin entry-point names through
   ``available_plugins()``. Listing reads distribution metadata and never
   imports plugin code, so it is safe to run anywhere.
2. The explicit ``--opt-in-load`` flag is the one moment third-party code
   runs: ``discover_plugins(registry)`` imports and invokes each registrar
   against a fresh registry. Nothing is loaded without that flag.

Run it locally from a repository clone:

    python examples/plugin_discovery_demo.py
    python examples/plugin_discovery_demo.py --opt-in-load
"""

from __future__ import annotations

import argparse
import sys

from dq_questionbank import (
    PLUGIN_ENTRY_POINT_GROUP,
    FormatRegistry,
    available_plugins,
    default_registry,
    discover_plugins,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the safe plugin discovery flow.")
    parser.add_argument(
        "--group",
        default=PLUGIN_ENTRY_POINT_GROUP,
        help="Entry-point group to inspect (default: the public plugin group).",
    )
    parser.add_argument(
        "--opt-in-load",
        action="store_true",
        help=(
            "Also run discover_plugins(), the only step that executes "
            "installed third-party code. Off by default."
        ),
    )
    args = parser.parse_args(argv)

    names = available_plugins(group=args.group)
    print(f"entry-point group: {args.group}")
    print(f"installed plugins (listing only, nothing loaded): {len(names)}")
    for name in names:
        print(f"  - {name}")

    if not args.opt_in_load:
        print("listing is read-only; pass --opt-in-load to run discover_plugins()")
        return 0

    registry: FormatRegistry = default_registry()
    loaded = discover_plugins(registry, group=args.group)
    print(f"opt-in discovery invoked registrars for: {len(loaded)} plugin(s)")
    for name in loaded:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
