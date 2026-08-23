# Quality-finding contract fixtures

These original synthetic specimens back the public revision-bound quality
finding contract (`dq_questionbank.quality_findings`). Each fixture pairs a
question payload with a serialized finding and the expected state:

- `current.json` — the finding still matches the question it was detected
  on (`finding_state` returns `current`).
- `stale.json` — the same finding against an edited stem block; the
  fingerprinted input no longer matches, so the state is `stale` and any
  judgment fails closed with `StaleFindingError`.
- `accepted.json` — a current finding plus a serialized accepted judgment
  whose `finding_fingerprint` binds the exact finding.
- `rejected.json` — the same shape with a rejected judgment.

The demonstration rule is `latex-mismatched-delimiters` over the malformed
`(x+1]` interval, so the fixtures exercise the same deterministic rules the
library ships. Cross-field staleness (any declared input dependency
changing) is covered directly in `tests/test_quality_findings.py`.

The fixtures contain no source question content, private data, or external
assets. See `provenance.json` for redistribution status.
