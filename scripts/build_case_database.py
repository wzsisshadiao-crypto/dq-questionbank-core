"""Build the bundled synthetic SQLite case from its auditable JSON source."""

from pathlib import Path

from dq_questionbank_local.case_database import build_case_database


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    build_case_database(
        ROOT / "examples" / "synthetic-case-source.json",
        ROOT / "src" / "dq_questionbank_local" / "data" / "synthetic-case.sqlite3",
    )
