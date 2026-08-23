"""The public asset-evidence contract for image repair.

The visual workspace reserves an ``Image Repair`` entry for the workflow
where a question embeds a raster asset whose bytes are wrong or missing.
The public contract below defines the **evidence** such a repair needs:

- which question block points at the asset;
- the asset reference and the digest of the bytes currently bound;
- the digest of the proposed replacement bytes, reachable through a
  safe relative path under an assets root the caller owns.

Binding and previewing are the only operations in the core:

- :func:`bind_asset_repair` validates the block path, resolves the asset
  on the canonical question (unknown assets and digest-less bindings
  fail closed), and validates the replacement path against the same
  safe-relative-path rules the storage adapters enforce;
- :func:`preview_asset_repair` re-verifies both digests against the
  bytes actually on disk and returns a preview record.

There is deliberately **no accept-and-write step here**: the contract
never moves or overwrites bytes. A caller that decides to apply a
previewed repair does so in its own storage layer, with its own atomic
write and its own rollback.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .models import Question

STATUS_PROPOSED = "proposed"
_STATUSES = (STATUS_PROPOSED,)

_PROPOSAL_FIELDS = {
    "question_id",
    "target_field",
    "asset_id",
    "asset_uri",
    "current_sha256",
    "replacement_path",
    "replacement_sha256",
    "status",
}

_BLOCK_PATH_RE = re.compile(r"^(stem|solution)\.blocks\[(\d+)\]$")


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_replacement_path(assets_root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``assets_root`` with traversal rejected."""
    if not isinstance(relative, str) or not relative:
        raise ValueError("A replacement path is required.")
    if "\\" in relative or "\x00" in relative:
        raise ValueError("Replacement paths must use forward slashes only.")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in ("..", "") for part in pure.parts) or relative.startswith("/"):
        raise ValueError("Replacement paths must stay inside the assets root.")
    if len(pure.parts) > 8:
        raise ValueError("Replacement paths may nest at most 8 levels.")
    root = assets_root.resolve()
    target = (root / Path(*pure.parts)).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Replacement path escaped the assets root.")
    if target.is_symlink():
        raise ValueError("Refusing to read a replacement through a symbolic link.")
    return target


@dataclass(frozen=True, slots=True)
class AssetRepairProposal:
    """One previewed image-repair proposal bound to its evidence.

    ``current_sha256`` is the digest recorded on the canonical question's
    asset; ``replacement_sha256`` is the digest of the proposed bytes at
    ``replacement_path`` under the caller's assets root. Both are pinned
    at bind time so any later drift is detectable at preview time.
    """

    question_id: str
    target_field: str
    asset_id: str
    asset_uri: str
    current_sha256: str
    replacement_path: str
    replacement_sha256: str
    status: str = STATUS_PROPOSED

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "target_field": self.target_field,
            "asset_id": self.asset_id,
            "asset_uri": self.asset_uri,
            "current_sha256": self.current_sha256,
            "replacement_path": self.replacement_path,
            "replacement_sha256": self.replacement_sha256,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetRepairProposal:
        unknown = sorted(set(data) - _PROPOSAL_FIELDS)
        if unknown:
            raise ValueError(f"Unknown asset-repair field(s): {', '.join(unknown)}.")
        status = str(data["status"])
        if status not in _STATUSES:
            raise ValueError(f"Unsupported asset-repair status: {status!r}.")
        return cls(
            question_id=str(data["question_id"]),
            target_field=str(data["target_field"]),
            asset_id=str(data["asset_id"]),
            asset_uri=str(data["asset_uri"]),
            current_sha256=str(data["current_sha256"]),
            replacement_path=str(data["replacement_path"]),
            replacement_sha256=str(data["replacement_sha256"]),
            status=status,
        )


def _resolve_image_block(question: Question, target_field: str):
    match = _BLOCK_PATH_RE.match(target_field) if isinstance(target_field, str) else None
    if match is None:
        raise ValueError(f"Unsupported asset-repair field path: {target_field!r}.")
    field_name, index = match.group(1), int(match.group(2))
    content = getattr(question, field_name, None)
    blocks = content.blocks if content is not None else []
    if index >= len(blocks):
        raise ValueError(f"Block path {target_field!r} does not exist on the question.")
    block = blocks[index]
    if block.type != "image":
        raise ValueError(f"Block path {target_field!r} is not an image block.")
    return block


def bind_asset_repair(
    question: Question,
    target_field: str,
    asset_id: str,
    replacement_path: str,
    assets_root: Path,
) -> AssetRepairProposal:
    """Bind a repair proposal to the question's recorded asset evidence.

    Fails closed when the block path is invalid, the asset id does not
    match the block or the question's assets, the asset carries no
    digest, or the replacement path escapes the assets root.
    """
    block = _resolve_image_block(question, target_field)
    if not asset_id or block.asset_id != asset_id:
        raise ValueError(
            f"Block {target_field!r} does not reference asset {asset_id!r}."
        )
    asset = next(
        (item for item in question.assets or [] if item.id == asset_id), None
    )
    if asset is None:
        raise ValueError(f"Asset {asset_id!r} is not declared on the question.")
    if not asset.sha256:
        raise ValueError(f"Asset {asset_id!r} has no digest to bind as evidence.")
    target = _safe_replacement_path(Path(assets_root), replacement_path)
    if not target.is_file():
        raise ValueError(f"Replacement file not found: {replacement_path!r}.")
    return AssetRepairProposal(
        question_id=question.id,
        target_field=target_field,
        asset_id=asset_id,
        asset_uri=asset.uri,
        current_sha256=asset.sha256,
        replacement_path=replacement_path,
        replacement_sha256=_digest_file(target),
    )


def preview_asset_repair(
    proposal: AssetRepairProposal,
    question: Question,
    assets_root: Path,
) -> dict[str, Any]:
    """Re-verify a proposal against the bytes on disk and return a preview.

    This is the preview-only application step: it validates that the
    question still binds the same asset digest, that the replacement
    bytes still match the digest pinned at bind time, and reports both
    sizes for the reviewer. It never moves, writes, or overwrites
    anything — applying a previewed repair is the caller's own storage
    operation.
    """
    if proposal.status != STATUS_PROPOSED:
        raise ValueError("Only a proposed asset repair can be previewed.")
    _resolve_image_block(question, proposal.target_field)
    asset = next(
        (item for item in question.assets or [] if item.id == proposal.asset_id), None
    )
    if asset is None:
        raise ValueError(
            f"Asset {proposal.asset_id!r} is no longer present on the question."
        )
    if asset.sha256 != proposal.current_sha256:
        raise ValueError(
            f"Asset {proposal.asset_id!r} digest changed since binding; "
            "re-bind the repair proposal."
        )
    target = _safe_replacement_path(Path(assets_root), proposal.replacement_path)
    if not target.is_file():
        raise ValueError(
            f"Replacement file is missing: {proposal.replacement_path!r}."
        )
    actual = _digest_file(target)
    if actual != proposal.replacement_sha256:
        raise ValueError(
            "Replacement bytes changed since binding; re-bind the repair proposal."
        )
    return {
        "question_id": proposal.question_id,
        "target_field": proposal.target_field,
        "asset_id": proposal.asset_id,
        "asset_uri": proposal.asset_uri,
        "current_sha256": proposal.current_sha256,
        "replacement_sha256": proposal.replacement_sha256,
        "replacement_bytes": target.stat().st_size,
        "applied": False,
        "note": "Preview only: the core never moves or overwrites asset bytes.",
    }

