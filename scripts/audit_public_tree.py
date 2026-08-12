"""Fail closed on common private-data and repository hygiene mistakes."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".pytest_cache",
    ".ruff_cache",
}
FORBIDDEN_PARTS = {"uploads", "backups", "logs", "private", "secrets"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".p12", ".pfx"}
MAX_FILE_SIZE = 5 * 1024 * 1024
TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".html",
    ".css",
    ".js",
    ".txt",
    ".example",
}
SECRET_RULES = {
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "non-empty API key assignment": re.compile(
        r"(?i)[\"']?(?:api[_-]?key|access[_-]?token|secret)[\"']?\s*[:=]\s*[\"'][^\s\"']{12,}[\"']"
    ),
}


def audit(root: Path = ROOT) -> list[tuple[Path, str]]:
    findings: list[tuple[Path, str]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.is_dir():
            if any(part.lower() in FORBIDDEN_PARTS for part in relative.parts):
                findings.append((relative, "forbidden private-data directory"))
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append((relative, "forbidden file type"))
        if path.stat().st_size > MAX_FILE_SIZE:
            findings.append((relative, "file exceeds 5 MiB review limit"))
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append((relative, "text file is not valid UTF-8"))
            continue
        for rule_name, pattern in SECRET_RULES.items():
            if pattern.search(text):
                findings.append((relative, rule_name))
    return findings


def main() -> int:
    findings = audit()
    if findings:
        print(
            "Public-tree audit failed. Matched values are intentionally not displayed.",
            file=sys.stderr,
        )
        for path, rule in findings:
            print(f"- {path}: {rule}", file=sys.stderr)
        return 1
    file_count = sum(
        1
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts)
    )
    print(f"Public-tree audit passed for {file_count} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
