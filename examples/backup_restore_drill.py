"""A safe backup-and-restore drill for a local question workspace.

The drill runs four phases on a caller-chosen workspace directory, using
only the Python standard library:

1. **backup** - copy every regular file into a new backup directory and
   write a ``manifest.json`` recording each file's relative path and
   SHA-256 digest;
2. **verify** - re-read the backup and re-digest every manifest entry;
   any mismatch, missing entry, or extra file fails verification;
3. **restore** - copy the verified files back over the workspace
   (refusing to write through symbolic links);
4. **compare** - re-digest the restored workspace and confirm it is
   byte-identical to the manifest.

Exit code is ``0`` only when every phase passes; any mismatch exits
non-zero with a message on stderr.

Run it against a synthetic workspace, never production or private data:

    python examples/backup_restore_drill.py --workspace path/to/workspace
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

MANIFEST_NAME = "manifest.json"


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workspace_files(root: Path) -> list[Path]:
    return sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and not item.is_symlink()
    )


def backup(workspace: Path, backup_dir: Path) -> Path:
    """Copy every workspace file into ``backup_dir`` with a digest manifest."""
    if backup_dir.exists():
        raise SystemExit(f"backup directory already exists: {backup_dir}")
    backup_dir.mkdir(parents=True)
    entries = []
    for source in _workspace_files(workspace):
        relative = source.relative_to(workspace).as_posix()
        target = backup_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise SystemExit(f"refusing to write backup through symlink: {relative}")
        shutil.copy2(source, target)
        entries.append({"path": relative, "sha256": _digest_file(target)})
    manifest = backup_dir / MANIFEST_NAME
    manifest.write_text(
        json.dumps({"workspace_files": entries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify(backup_dir: Path) -> list[dict[str, str]]:
    """Re-digest every manifest entry; raise SystemExit on any mismatch."""
    manifest_path = backup_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise SystemExit(f"backup manifest is missing: {manifest_path}")
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))[
        "workspace_files"
    ]
    listed = {entry["path"] for entry in entries}
    present = {
        item.relative_to(backup_dir).as_posix()
        for item in _workspace_files(backup_dir)
        if item != manifest_path
    }
    missing = sorted(listed - present)
    extra = sorted(present - listed)
    if missing:
        raise SystemExit(f"backup is missing files: {missing}")
    if extra:
        raise SystemExit(f"backup contains unmanifested files: {extra}")
    for entry in entries:
        target = backup_dir / entry["path"]
        actual = _digest_file(target)
        if actual != entry["sha256"]:
            raise SystemExit(
                f"backup digest mismatch for {entry['path']}: "
                f"manifest={entry['sha256']} actual={actual}"
            )
    return entries


def restore(workspace: Path, backup_dir: Path, entries: list[dict[str, str]]) -> None:
    """Copy verified backup files back over the workspace."""
    for entry in entries:
        source = backup_dir / entry["path"]
        target = workspace / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise SystemExit(f"refusing to restore through symlink: {entry['path']}")
        shutil.copy2(source, target)


def compare(workspace: Path, entries: list[dict[str, str]]) -> None:
    """Confirm the restored workspace is byte-identical to the manifest."""
    actual = {
        item.relative_to(workspace).as_posix(): _digest_file(item)
        for item in _workspace_files(workspace)
    }
    expected = {entry["path"]: entry["sha256"] for entry in entries}
    if actual != expected:
        raise SystemExit("restored workspace does not match the backup manifest")


def run_drill(workspace: Path, backup_dir: Path | None = None) -> Path:
    """Run backup -> verify -> restore -> compare and return the backup dir."""
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise SystemExit(f"workspace directory does not exist: {workspace}")
    if backup_dir is None:
        backup_dir = workspace.parent / f"{workspace.name}.backup-drill"
    backup_dir = backup_dir.resolve()
    backup(workspace, backup_dir)
    entries = verify(backup_dir)
    restore(workspace, backup_dir, entries)
    compare(workspace, entries)
    return backup_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Workspace directory to drill against (use synthetic data).",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Backup directory to create (default: <workspace>.backup-drill).",
    )
    args = parser.parse_args(argv)
    try:
        backup_dir = run_drill(args.workspace, args.backup_dir)
    except SystemExit as exc:
        print(f"drill failed: {exc}", file=sys.stderr)
        return 1
    print(f"backup verified and restored: {backup_dir}")
    print("workspace is byte-identical to the pre-drill state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

