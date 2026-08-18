"""Build the static bilingual product site without network dependencies."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_SOURCE = ROOT / "site"
SCREENSHOTS = (
    ROOT / "docs" / "assets" / "question-bank-workspace.png",
    ROOT / "docs" / "assets" / "question-bank-workspace-zh.png",
)


def build_site(output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"site output already exists: {output}")
    shutil.copytree(SITE_SOURCE, output)
    asset_output = output / "assets"
    for screenshot in SCREENSHOTS:
        shutil.copy2(screenshot, asset_output / screenshot.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    build_site(args.output.resolve())
    print(f"Bilingual site built at {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
