# OSS Readiness Report

Assessment date: 2026-08-12

## Scores

| Area | Score | Notes |
|---|---:|---|
| Architecture | 9/10 | Independent canonical core with one-way private adapter boundary. |
| Documentation | 9/10 | README, architecture, schema, formats, compatibility, roadmap, and contribution docs are present. |
| Testing | 8/10 | Core behaviors and four formats are covered; more cross-application DOCX fixtures are needed. |
| Security | 8/10 | Local-only UI, safe asset paths, no provider calls, and fail-closed public-tree audit. |
| Privacy | 9/10 | Allowlist extraction and synthetic fixtures; no private content copied. |
| Contributor Experience | 9/10 | Editable install, CLI, tests, templates, and extension documentation. |
| Release Readiness | 7/10 | Package metadata, CI, changelog, and versioning exist; final license and credentials remain blockers. |
| Open-source Independence | 10/10 | No import, database, service, or runtime dependency on the private application. |

## Verified locally

- 30 unit and integration tests passed on Python 3.12.
- Ruff lint and formatting checks passed for `src`, `tests`, and `scripts`.
- The normative JSON Schema validated both itself and the synthetic sample.
- The public-tree secret and private-data audit passed.
- All relative Markdown links resolved.
- The browser application's JavaScript passed a syntax check, its HTTP endpoint returned the
  expected English page, and static accessibility assertions passed.
- A wheel was built, inspected for its expected payload, installed in a clean virtual
  environment, and used for JSON-to-Markdown-to-JSON conversion and validation.
- Source-distribution creation remains covered by GitHub CI; the local build frontend needed for
  that additional check could not be installed in the preparation environment.

Automated browser screenshot capture was unavailable in the preparation environment. This does
not block the local-only alpha, but interactive visual QA should be repeated before a tagged
release.

## Blockers

1. Select an OSI-approved license, add the exact `LICENSE` text, and update package metadata.
2. Revoke and rotate the live-looking credentials found in the private `backend/ai_config.json`. Even though the file is absent from this repository, rotation is required because the value has existed in an unmanaged local source tree.
3. Before the first push, initialize a new Git repository in this directory only and inspect the complete staged file list. Do not attach the private repository's history.
4. Confirm the GitHub repository visibility and branch strategy before pushing.
5. Perform a final interactive visual check of the playground in a supported browser.

## Recommended before 0.2

- Add independently authored DOCX fixtures from at least two office suites.
- Add a formal schema migration API when a second schema version exists.
- Add property-based tests for nested content and malformed input.
- Enable GitHub private vulnerability reporting and branch protection.

## Optional

- Add an IMS QTI research adapter.
- Publish a conformance corpus under explicit fixture licenses.
- Add signed release artifacts and provenance attestations.

## Final answer

```text
Is this repository safe to make public?

YES, AFTER FIXING THE FOLLOWING ITEMS:
- choose and add the license;
- revoke and rotate the private-tree credentials;
- perform the final staged-file review in a newly initialized repository.
```

No public upload was performed during this preparation.
