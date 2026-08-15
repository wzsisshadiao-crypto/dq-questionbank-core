# Stable Public Python API

The package-level exports in `dq_questionbank.__all__`, together with the
documented model, registry, and reference-storage methods, are the stable
public Python API surface. The checked-in
[`public-api-manifest.json`](public-api-manifest.json) records their names,
kinds, and callable signatures.

Run the compatibility check locally:

```bash
python scripts/check_public_api.py
```

The command fails when a stable export or documented member is removed,
renamed, or given an incompatible signature. It runs in CI on every supported
Python version.

When a deliberate public API change is approved with the required compatibility
notes and release-version change, regenerate the manifest explicitly:

```bash
python scripts/check_public_api.py --write
```

Do not use the write mode to hide an accidental API break. The manifest tracks
the Python package surface only; JSON schema compatibility is covered by the
fixture suite described in [Compatibility Fixtures](compatibility-fixtures.md).
