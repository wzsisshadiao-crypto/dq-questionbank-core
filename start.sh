#!/bin/sh
# Launcher for the DQ QuestionBank local workspace (Python 3.10 or newer).
# Usage: sh start.sh   (or ./start.sh after making it executable)
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
    exec python3 run.py "$@"
fi
if command -v python >/dev/null 2>&1; then
    exec python run.py "$@"
fi
echo "Python 3.10+ was not found. Install it from https://www.python.org/downloads/" >&2
exit 1
