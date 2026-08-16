"""Run the visual local workspace from a source checkout."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dq_questionbank_local.cli import main  # noqa: E402

raise SystemExit(main(["--open-browser", *sys.argv[1:]]))
