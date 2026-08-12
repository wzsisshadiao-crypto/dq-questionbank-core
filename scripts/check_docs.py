"""Check that relative links in public Markdown documents resolve."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
IGNORED_PARTS = {".git", ".venv", "build", "dist", "venv"}


def find_broken_links(root: Path = ROOT) -> list[tuple[Path, str]]:
    broken: list[tuple[Path, str]] = []
    for document in root.rglob("*.md"):
        relative_document = document.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative_document.parts):
            continue
        for destination in LINK_PATTERN.findall(document.read_text(encoding="utf-8")):
            destination = destination.strip().strip("<>").split(maxsplit=1)[0]
            if destination.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_text = unquote(destination.split("#", 1)[0])
            if path_text and not (document.parent / path_text).resolve().exists():
                broken.append((relative_document, destination))
    return broken


def main() -> int:
    broken = find_broken_links()
    if broken:
        print("Documentation link check failed:", file=sys.stderr)
        for document, destination in broken:
            print(f"- {document}: {destination}", file=sys.stderr)
        return 1
    print("Documentation link check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
