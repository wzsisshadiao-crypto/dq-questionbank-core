"""Shared identity rules for the managed PDF import pipeline.

Import jobs are named after their canonical paper tag (for example
``AH2026``), but runtime tooling appends well-known namespace suffixes such
as ``AH2026_JOB`` or ``AH2026_20260825_W3``. Deciding "does this job belong
to this paper?" must not depend on fragile prefix guessing, so the rule is
explicit: a job matches a tag when it equals the normalized tag or extends
it with exactly one known runtime namespace.

Example::

    normalize_import_tag("ah 2026")  # "AH_2026"
    job_matches_tag("AH_2026_JOB", "AH2026")  # True
    job_matches_tag("AH_2026_XYZ", "AH2026")  # False
"""

from __future__ import annotations

import re

_TAG_GLUE_RE = re.compile(r"([A-Za-z]+)(\d)")
_RUNTIME_JOB_SUFFIX_RE = re.compile(
    r"^_(?:JOB|BATCH|RUN|PDFREG|NEWLOGIC|(?:\d{8}_)?W\d*)(?:_|$)"
)


def normalize_import_tag(tag: str) -> str:
    """Normalize ``AH2026`` and ``ah_2026`` (and ``ah 2026``) to ``AH_2026``."""
    value = _TAG_GLUE_RE.sub(r"\1_\2", str(tag or "").strip().upper())
    value = value.replace(" ", "_")
    return re.sub(r"_+", "_", value).strip("_")


def job_matches_tag(job_id: str, tag: str) -> bool:
    """Return True when a job id is a canonical tag plus one runtime namespace.

    The comparison happens on normalized forms; unknown suffixes (a prefix
    of another paper's tag, free text, ...) never match.
    """
    normalized_tag = normalize_import_tag(tag)
    normalized_job = normalize_import_tag(job_id)
    if not normalized_tag:
        return False
    if normalized_job == normalized_tag:
        return True
    if not normalized_job.startswith(normalized_tag + "_"):
        return False
    return bool(_RUNTIME_JOB_SUFFIX_RE.match(normalized_job[len(normalized_tag):]))


__all__ = ["job_matches_tag", "normalize_import_tag"]
