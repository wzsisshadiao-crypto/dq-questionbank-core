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

## Word publishing API

Version 0.8 adds the following stable package exports:

- `build_envelope`, `validate_envelope`, and `question_fingerprint` define the
  revision-bound publishing contract.
- `export_word_publishing` and `extract_managed_blocks` write and inspect
  managed Word content controls.
- `WordPublisher` performs ordered refresh and stale retention.
- `WordPublishingBridge` serves explicit insert and refresh requests on a
  loopback address.
- `word_macro_source` returns the VBA module bundled in the wheel.

`ENVELOPE_VERSION` identifies the publishing protocol independently from the
canonical question schema and Python package version. See
[Word Publishing](word-publishing-envelope.md) for the full behavioral and
security contract.

## LaTeX repair API

The package exports the first deterministic quality repair rule:

- `repair_latex_braces` proposes a one-step repair for a LaTeX source that is
  missing exactly one closing brace and is otherwise intact.
- `LatexRepairOutcome` keeps the original source visible, carries the stable
  rule id (`latex-missing-closing-brace`) when a repair is proposed, and a
  finding code when the damage is ambiguous and must stay in manual review.

Missing opening braces, multiple breaks, and trailing escapes are never
rewritten; they are reported as findings instead. This is the first bounded
slice of the deterministic repair rule set described in the
[Correction Rule Workflow](correction-rule-workflow.md).
