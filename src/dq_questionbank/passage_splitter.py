"""Separate a shared reading passage from per-question stems.

Reading-comprehension imports often repeat the same passage as the leading
blocks of every question stem in a batch. This module detects that shared
prefix and returns it as standalone ``shared_blocks`` plus the remaining
per-question stem blocks, so callers can model one passage with several
questions instead of duplicating the passage.

The split is conservative and pure: the input ``QuestionSet`` is never
mutated, and only blocks whose serialized ``to_dict()`` payloads are
byte-identical across ALL questions are lifted. A lift happens only when
the set holds at least two questions, the common leading prefix contains at
least one block, and every question keeps at least one distinct block of
its own; otherwise the batch is returned unchanged with one canonical
reason. Part of #92.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import QuestionSet

PASSAGE_SPLIT_VERSION = "passage-split/1"

REASON_SINGLE_QUESTION = "single-question"
REASON_NO_COMMON_PREFIX = "no-common-prefix"
REASON_EMPTY_REMAINDER = "empty-remainder"

_SPLIT_FIELDS = {"changed", "shared_blocks", "question_stems", "reasons"}
_STEM_FIELDS = {"question_id", "blocks"}


@dataclass(frozen=True, slots=True)
class PassageSplit:
    """The outcome of shared-passage splitting over one question set.

    ``shared_blocks`` holds the lifted serialized passage blocks and
    ``question_stems`` pairs each question id with its remaining stem
    blocks; both are empty when the set is unchanged, in which case
    ``reasons`` carries exactly one canonical reason for the refusal.
    """

    changed: bool
    shared_blocks: tuple[dict[str, Any], ...]
    question_stems: tuple[tuple[str, tuple[dict[str, Any], ...]], ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "shared_blocks": [dict(block) for block in self.shared_blocks],
            "question_stems": [
                {"question_id": question_id, "blocks": [dict(block) for block in blocks]}
                for question_id, blocks in self.question_stems
            ],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PassageSplit:
        unknown = sorted(set(data) - _SPLIT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown passage-split field(s): {', '.join(unknown)}.")
        raw_stems = data["question_stems"]
        if not isinstance(raw_stems, list):
            raise ValueError("Passage-split question stems must be a list.")
        stems: list[tuple[str, tuple[dict[str, Any], ...]]] = []
        for item in raw_stems:
            if not isinstance(item, dict):
                raise ValueError("Passage-split question stems must be objects.")
            unknown_stem = sorted(set(item) - _STEM_FIELDS)
            if unknown_stem:
                raise ValueError(
                    f"Unknown passage-split stem field(s): {', '.join(unknown_stem)}."
                )
            raw_blocks = item["blocks"]
            if not isinstance(raw_blocks, list):
                raise ValueError("Passage-split stem blocks must be a list.")
            stems.append((str(item["question_id"]), tuple(dict(b) for b in raw_blocks)))
        return cls(
            changed=bool(data["changed"]),
            shared_blocks=tuple(dict(block) for block in data["shared_blocks"]),
            question_stems=tuple(stems),
            reasons=tuple(str(item) for item in data["reasons"]),
        )


def _rendered_stems(questions: list) -> list[list[dict[str, Any]]]:
    """Serialize every question's stem blocks into comparable payloads."""
    return [[block.to_dict() for block in question.stem.blocks] for question in questions]


def _common_prefix_length(rendered: list[list[dict[str, Any]]]) -> int:
    """Return the number of leading blocks identical across all questions."""
    limit = min(len(blocks) for blocks in rendered)
    length = 0
    while length < limit and all(
        blocks[length] == rendered[0][length] for blocks in rendered
    ):
        length += 1
    return length


def split_shared_passage(question_set: QuestionSet) -> PassageSplit:
    """Lift the shared leading passage from a batch of stems (pure function).

    The common prefix is computed over serialized block payloads, so only
    blocks identical across ALL questions are lifted. The lift happens only
    for sets of two or more questions whose common prefix is non-empty and
    whose every question keeps at least one distinct block; anything else is
    returned unchanged with one canonical reason. The input question set is
    never mutated.
    """
    questions = list(question_set.questions)
    if len(questions) < 2:
        return PassageSplit(False, (), (), (REASON_SINGLE_QUESTION,))
    rendered = _rendered_stems(questions)
    prefix = _common_prefix_length(rendered)
    if prefix < 1:
        return PassageSplit(False, (), (), (REASON_NO_COMMON_PREFIX,))
    if any(len(blocks) <= prefix for blocks in rendered):
        return PassageSplit(False, (), (), (REASON_EMPTY_REMAINDER,))
    question_stems = tuple(
        (question.id, tuple(blocks[prefix:]))
        for question, blocks in zip(questions, rendered, strict=True)
    )
    return PassageSplit(
        changed=True,
        shared_blocks=tuple(rendered[0][:prefix]),
        question_stems=question_stems,
        reasons=(),
    )

