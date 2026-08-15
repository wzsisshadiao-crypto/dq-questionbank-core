"""Deterministically export and check the repository-owned Wiki source."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIKI_SOURCE = ROOT / "docs" / "wiki"
MANIFEST_PATH = WIKI_SOURCE / "manifest.json"


def source_pages(source: Path = WIKI_SOURCE) -> tuple[Path, ...]:
    """Return the flat set of canonical Wiki pages in a stable order."""
    return tuple(sorted(path for path in source.glob("*.md") if path.is_file()))


def manifest_payload(source: Path = WIKI_SOURCE) -> dict[str, object]:
    pages = source_pages(source)
    return {
        "format_version": 1,
        "files": {
            page.name: hashlib.sha256(page.read_bytes()).hexdigest()
            for page in pages
        },
    }


def write_manifest(source: Path = WIKI_SOURCE) -> None:
    MANIFEST_PATH.write_text(
        json.dumps(manifest_payload(source), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def check_manifest(source: Path = WIKI_SOURCE) -> list[str]:
    if not MANIFEST_PATH.is_file():
        return [f"Missing Wiki manifest: {MANIFEST_PATH}"]
    try:
        recorded = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Invalid Wiki manifest: {exc}"]
    expected = manifest_payload(source)
    if recorded == expected:
        return []
    return ["Wiki manifest is stale; run python scripts/wiki_sync.py write-manifest"]


def _validate_destination(destination: Path, *, allow_empty: bool) -> Path:
    destination = destination.resolve()
    if destination == WIKI_SOURCE.resolve():
        raise ValueError("Wiki destination must not be the canonical docs/wiki source")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Wiki destination is not a directory: {destination}")
    if destination.exists() and not allow_empty and any(destination.iterdir()):
        raise ValueError(f"Wiki export destination must be empty: {destination}")
    return destination


def export_wiki(destination: Path, source: Path = WIKI_SOURCE) -> tuple[str, ...]:
    """Materialize canonical pages into an empty target directory."""
    destination = _validate_destination(destination, allow_empty=False)
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for page in source_pages(source):
        target = destination / page.name
        target.write_bytes(page.read_bytes())
        written.append(page.name)
    return tuple(written)


def sync_wiki(destination: Path, source: Path = WIKI_SOURCE) -> tuple[str, ...]:
    """Update canonical page names in an existing target without deleting files."""
    destination = _validate_destination(destination, allow_empty=True)
    if not destination.is_dir():
        raise ValueError(f"Wiki sync destination does not exist: {destination}")
    updated = []
    for page in source_pages(source):
        target = destination / page.name
        content = page.read_bytes()
        if not target.is_file() or target.read_bytes() != content:
            target.write_bytes(content)
            updated.append(page.name)
    return tuple(updated)


def check_wiki(destination: Path, source: Path = WIKI_SOURCE) -> list[str]:
    """Report missing, stale, and extra Markdown pages without writing anything."""
    destination = _validate_destination(destination, allow_empty=True)
    if not destination.is_dir():
        return [f"Wiki destination does not exist: {destination}"]
    expected = {page.name: page.read_bytes() for page in source_pages(source)}
    actual = {page.name: page.read_bytes() for page in destination.glob("*.md") if page.is_file()}
    drift = []
    for name in sorted(expected):
        if name not in actual:
            drift.append(f"Missing Wiki page: {name}")
        elif actual[name] != expected[name]:
            drift.append(f"Stale Wiki page: {name}")
    for name in sorted(set(actual) - set(expected)):
        drift.append(f"Extra Wiki page: {name}")
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "export", "sync"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("destination", type=Path)
    subparsers.add_parser("check-manifest")
    subparsers.add_parser("write-manifest")
    args = parser.parse_args(argv)

    if args.command == "check-manifest":
        drift = check_manifest()
        if drift:
            print("Wiki source check failed:", file=sys.stderr)
            print("\n".join(f"- {item}" for item in drift), file=sys.stderr)
            return 1
        print("Wiki source manifest is current.")
        return 0
    if args.command == "write-manifest":
        write_manifest()
        print(f"Wrote {MANIFEST_PATH.relative_to(ROOT)}")
        return 0

    try:
        if args.command == "export":
            pages = export_wiki(args.destination)
            print(f"Exported {len(pages)} Wiki page(s).")
            return 0
        if args.command == "sync":
            pages = sync_wiki(args.destination)
            print(f"Synced {len(pages)} Wiki page(s).")
            return 0
        drift = check_wiki(args.destination)
    except ValueError as exc:
        parser.error(str(exc))
    if drift:
        print("Wiki drift detected:", file=sys.stderr)
        print("\n".join(f"- {item}" for item in drift), file=sys.stderr)
        return 1
    print("Wiki target matches the canonical source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
