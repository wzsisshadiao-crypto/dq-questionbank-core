# Asset-repair contract fixtures

This original synthetic specimen pair backs the public asset-evidence
contract (`dq_questionbank.asset_repair`). The fixture embeds two
deterministic 1x1 grayscale PNGs (base64-encoded with pinned SHA-256
digests) - an original bound to a question's asset declaration and a
proposed replacement - plus the canonical question payload referencing
the original.

Expected behavior, executed by `tests/test_asset_repair.py`:

- binding pins the block path, asset reference, current digest, and the
  replacement digest;
- previewing re-verifies both digests against the bytes on disk and
  never moves or overwrites anything;
- unknown assets, non-image blocks, missing blocks, path traversal,
  current-digest drift, and replacement-byte drift all fail closed.

See `provenance.json` for redistribution status.
