# Release Checklist

Use this checklist for every public release. The first four items are mandatory before the
initial GitHub push.

## Legal and private-source boundary

- [ ] Select an OSI-approved license and add the exact `LICENSE` text.
- [ ] Revoke and rotate credentials identified in the private source tree.
- [ ] Confirm that every example and fixture is synthetic, original, public-domain, or clearly
      licensed.
- [ ] Confirm that no private Git history is attached to this directory.
- [ ] Review `OPEN_SOURCE_BOUNDARY.md` and reject any unexplained private implementation copy.

## Quality and security

- [ ] Run `python -m ruff check src tests scripts`.
- [ ] Run `python -m ruff format --check src tests scripts`.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `python scripts/audit_public_tree.py`.
- [ ] Run `python scripts/check_docs.py`.
- [ ] Build both wheel and source distribution with `python -m build`.
- [ ] Inspect archive filenames before publishing.
- [ ] Install the wheel in a clean virtual environment and run `dq --version`, `dq validate`,
      and one conversion round trip.
- [ ] Open `dq serve` in a supported browser and check desktop and narrow layouts.

## GitHub release controls

- [ ] Review the complete staged file list and staged diff.
- [ ] Confirm repository visibility, default branch, branch protection, and private vulnerability
      reporting.
- [ ] Confirm the version in `pyproject.toml` and the matching `CHANGELOG.md` entry.
- [ ] Confirm CI passes on Python 3.10, 3.11, and 3.12.
- [ ] Create a signed or annotated tag only after the commit is approved.
- [ ] Verify the public repository from a signed-out browser session.
