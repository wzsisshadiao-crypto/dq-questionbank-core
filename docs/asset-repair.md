# Asset-Evidence Contract for Image Repair

The visual workspace reserves an **Image Repair** entry for the workflow
where a question embeds a raster asset whose bytes are wrong or missing.
`dq_questionbank.asset_repair` defines the public evidence such a repair
needs — and deliberately nothing more.

## Binding

```python
from dq_questionbank import bind_asset_repair

proposal = bind_asset_repair(
    question,
    "stem.blocks[1]",            # the block that points at the asset
    "diagram-1",                 # the asset reference on the question
    "replacements/diagram-1-fixed.png",  # safe relative path under your assets root
    assets_root,
)
```

An `AssetRepairProposal` binds:

- the question id and the exact block path;
- the asset reference (`asset_id` / `asset_uri`) and the digest recorded
  on the question's asset declaration (`current_sha256`);
- the replacement path and the digest of the replacement bytes
  (`replacement_sha256`).

Binding fails closed on unknown assets, non-image blocks, missing
blocks, digest-less assets, and unsafe replacement paths. Replacement
paths follow the storage adapters' safe-relative-path rules: forward
slashes only, no absolute paths, no `..` segments, at most 8 levels of
nesting, containment under the assets root, and no symbolic links.

## Previewing

```python
from dq_questionbank import preview_asset_repair

preview = preview_asset_repair(proposal, question, assets_root)
```

The preview re-verifies that the question still binds the same digest
and that the replacement bytes on disk still match the digest pinned at
bind time, then reports both digests and the replacement size. Any drift
fails closed with instructions to re-bind.

**There is no accept-and-write step in the core.** The contract never
moves or overwrites bytes; a caller that decides to apply a previewed
repair does so in its own storage layer, with its own atomic write and
rollback — for example by combining this preview with the
[backup-and-restore drill](backup-restore.md).

The synthetic demonstration pair (a tiny original PNG plus its
replacement) lives in `tests/fixtures/asset-repair/`.
