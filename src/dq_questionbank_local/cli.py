"""Command-line entry point for the visual local workspace."""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

from .server import create_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the DQ QuestionBank Local workspace.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("workspace"),
        help="Local workspace directory.",
    )
    parser.add_argument("--port", type=int, default=8766, help="Loopback port (default: 8766).")
    parser.add_argument(
        "--case-database",
        type=Path,
        help="Reviewed SQLite case database to offer in the visual workspace.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the loopback workspace in the default browser after startup.",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    server = create_server(args.workspace, port=args.port, case_database=args.case_database)
    url = f"http://127.0.0.1:{args.port}"
    print(f"DQ QuestionBank Local: {url}")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0
