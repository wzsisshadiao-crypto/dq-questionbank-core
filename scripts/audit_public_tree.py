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
    "_site",
    ".pytest_cache",
    ".ruff_cache",
}
FORBIDDEN_PARTS = {"uploads", "backups", "logs", "private", "secrets"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".p12", ".pfx"}
REVIEWED_DATABASE_FILES = {
    Path("src/dq_questionbank_local/data/synthetic-case.sqlite3"),
}
REVIEWED_IMPORT_CASE_FILES = {
    Path("src/dq_questionbank/data/import_cases/web-ai/browser-draft.docx"): b"PK\x03\x04",
    Path("src/dq_questionbank/data/import_cases/coding-word/coding-source.docx"): b"PK\x03\x04",
    Path("src/dq_questionbank/data/import_cases/coding-pdf/worksheet.pdf"): b"%PDF-",
    Path("src/dq_questionbank/data/import_cases/coding-exam-omml/synthetic-exam.docx"): b"PK\x03\x04",
    Path("src/dq_questionbank/data/import_cases/pdf-table/structured-worksheet.pdf"): b"%PDF-",
}
MAX_REVIEWED_DATABASE_SIZE = 1024 * 1024
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
    ".in",
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
            if relative not in REVIEWED_DATABASE_FILES:
                findings.append((relative, "forbidden file type"))
            elif path.is_symlink():
                findings.append((relative, "reviewed database must not be a symbolic link"))
            elif path.stat().st_size > MAX_REVIEWED_DATABASE_SIZE:
                findings.append((relative, "reviewed database exceeds 1 MiB limit"))
            elif path.read_bytes()[:16] != b"SQLite format 3\x00":
                findings.append((relative, "reviewed database has an invalid SQLite header"))
        if path.suffix.lower() in {".docx", ".pdf"}:
            expected_header = REVIEWED_IMPORT_CASE_FILES.get(relative)
            if expected_header is None:
                findings.append((relative, "unreviewed binary document"))
            elif path.is_symlink():
                findings.append((relative, "reviewed import source must not be a symbolic link"))
            elif not path.read_bytes().startswith(expected_header):
                findings.append((relative, "reviewed import source has an invalid file header"))
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
