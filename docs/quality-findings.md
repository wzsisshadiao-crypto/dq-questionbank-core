# Revision-Bound Quality Findings

This document defines the public quality-finding contract shipped in
`dq_questionbank.quality_findings`. It is the boundary a Quality Center
frontend integrates against; it is not a complete quality engine.

## The contract

A `QualityFinding` binds one detected issue to an exact revision:

- `question_id` — the question the finding belongs to;
- `target_field` — the exact field path, such as `stem.blocks[1]` or
  `choices[0].content`, which a focused editor can jump to directly;
- `rule_id` — the stable rule identifier (for example
  `latex-mismatched-delimiters`);
- `ruleset_version` — the active ruleset (`quality/1`);
- `input_fingerprints` — SHA-256 fingerprints over **the fields the rule
  actually read**, not just the target field;
- `severity`, `explanation` — `error` / `warning` / `info` plus a
  human-readable message;
- optional `repair` — preview-only data (rule id, original source,
  proposed LaTeX, applied rule chain). Applying it is always an explicit
  caller decision; nothing in this module rewrites a question.

## Staleness and fail-closed judgment

`finding_state(finding, question)` returns `current` or `stale`. A finding
goes stale when the question id changed, the ruleset version differs, a
declared dependency no longer resolves, or any fingerprinted dependency's
content changed. Unrelated edits do not invalidate a finding.

`judge_finding(finding, question, decision)` records the human decision
(`accepted` or `rejected`) and binds the finding's own fingerprint. Judging
a stale finding raises `StaleFindingError` — an outdated judgment can never
silently apply. Detection, judgment, and persistence are three separate
operations by design.

## Detection

`detect_quality_findings(question)` runs the deterministic LaTeX rules over
every math block in the stem, solution, and choices. Failing sources become
`error` findings; deterministic repairs become `warning` findings carrying
preview data.

## Frontend handoff

The `target_field` path is the editor handoff contract: split on `.blocks[`
to resolve the field and block index, focus that field in the Editor
Center, and re-run detection after the save to recheck. The serialized
forms (`to_dict` / `from_dict`) are stable and covered by fixtures in
`tests/fixtures/quality/findings/` (current, stale, accepted, rejected).

## Cross-field rules

A rule that reads several fields declares all of them in
`input_fingerprints`. Changing **any** declared dependency makes the
finding stale, while unrelated field changes do not — the distinction
raised in the design discussion on issue #6.
