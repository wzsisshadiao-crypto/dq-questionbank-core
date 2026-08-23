"""Split a mixed-language stem into language-tagged segments.

Bilingual imports often interleave an English stem with its Chinese
counterpart inside one question. This module splits such a stem into
ordered ``{"language", "blocks"}`` segments — one per language run — only
when the segments are cleanly separable.

Text blocks are classified by script: a block whose characters fall in the
CJK unicode ranges is ``zh``, otherwise ``en``. Non-text blocks (math,
tables, images, ...) attach to the preceding text segment, and any that
precede all text attach to the first text segment. The split happens only
when both supported languages appear and each has at least one text block;
a single text block mixing both scripts is returned unchanged — this module
never guesses intra-block language boundaries. Part of #92.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Content

BILINGUAL_SPLIT_VERSION = "bilingual-split/1"
SUPPORTED_LANGUAGES = ("en", "zh")

LANGUAGE_EN = "en"
LANGUAGE_ZH = "zh"
_MIXED_SCRIPT = "mixed"

REASON_EMPTY_STEM = "empty-stem"
REASON_NO_TEXT_BLOCKS = "no-text-blocks"
REASON_MIXED_SCRIPT_BLOCK = "mixed-script-block"
REASON_SINGLE_LANGUAGE = "single-language"

_SPLIT_FIELDS = {"changed", "segments", "reasons"}
_SEGMENT_FIELDS = {"language", "blocks"}

# CJK ideograph, extension, and punctuation blocks used for script detection.
_CJK_RANGES = (
    (0x2E80, 0x2EFF),
    (0x3000, 0x303F),
    (0x31C0, 0x31EF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2FA1F),
    (0x30000, 0x3134A),
)


@dataclass(frozen=True, slots=True)
class BilingualSplit:
    """The outcome of bilingual splitting over one stem.

    ``segments`` holds ordered ``{"language", "blocks"}`` payloads and is
    empty when the stem is unchanged, in which case ``reasons`` carries
    exactly one canonical reason for the refusal.
    """

    changed: bool
    segments: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "segments": [dict(segment) for segment in self.segments],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BilingualSplit:
        unknown = sorted(set(data) - _SPLIT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown bilingual-split field(s): {', '.join(unknown)}.")
        raw_segments = data["segments"]
        if not isinstance(raw_segments, list):
            raise ValueError("Bilingual-split segments must be a list.")
        segments: list[dict[str, Any]] = []
        for item in raw_segments:
            if not isinstance(item, dict):
                raise ValueError("Bilingual-split segments must be objects.")
            unknown_segment = sorted(set(item) - _SEGMENT_FIELDS)
            if unknown_segment:
                raise ValueError(
                    f"Unknown bilingual-segment field(s): {', '.join(unknown_segment)}."
                )
            language = str(item["language"])
            if language not in SUPPORTED_LANGUAGES:
                raise ValueError(f"Unsupported segment language: {language!r}.")
            raw_blocks = item["blocks"]
            if not isinstance(raw_blocks, list):
                raise ValueError("Bilingual-segment blocks must be a list.")
            segments.append({"language": language, "blocks": list(raw_blocks)})
        return cls(
            changed=bool(data["changed"]),
            segments=tuple(segments),
            reasons=tuple(str(item) for item in data["reasons"]),
        )


def _is_cjk(char: str) -> bool:
    """Return True when one character falls in a CJK unicode range."""
    code = ord(char)
    return any(low <= code <= high for low, high in _CJK_RANGES)


def _classify_text(text: str) -> str:
    """Classify one text block as ``zh``, ``en``, or mixed-script.

    Digits, punctuation, and whitespace are script-neutral: only CJK
    characters and ASCII letters decide, so a Chinese sentence containing
    an isolated math variable still counts as ``zh`` only when no Latin
    letters appear, and any block holding both scripts is ``mixed``.
    """
    has_cjk = False
    has_latin = False
    for char in text:
        if _is_cjk(char):
            has_cjk = True
        elif char.isascii() and char.isalpha():
            has_latin = True
    if has_cjk and has_latin:
        return _MIXED_SCRIPT
    return LANGUAGE_ZH if has_cjk else LANGUAGE_EN


def split_bilingual_stem(stem: Content) -> BilingualSplit:
    """Split one mixed-language stem into language-tagged segments.

    Consecutive text blocks of the same language merge into one segment;
    non-text blocks attach to the preceding text segment (or to the first
    one when they lead the stem). The split is returned only when both
    ``en`` and ``zh`` text blocks are present; mixed-script single blocks,
    single-language stems, stems without text blocks, and empty stems are
    returned unchanged with one canonical reason. Pure: the input stem is
    never mutated.
    """
    blocks = list(stem.blocks)
    if not blocks:
        return BilingualSplit(False, (), (REASON_EMPTY_STEM,))
    segments: list[tuple[str, list]] = []
    languages: set[str] = set()
    pending: list = []
    for block in blocks:
        if block.type != "text":
            if segments:
                segments[-1][1].append(block)
            else:
                pending.append(block)
            continue
        language = _classify_text(block.text or "")
        if language == _MIXED_SCRIPT:
            return BilingualSplit(False, (), (REASON_MIXED_SCRIPT_BLOCK,))
        if segments and segments[-1][0] == language:
            segments[-1][1].append(block)
        else:
            segments.append((language, pending + [block]))
            pending = []
        languages.add(language)
    if not languages:
        return BilingualSplit(False, (), (REASON_NO_TEXT_BLOCKS,))
    if len(languages) < 2:
        return BilingualSplit(False, (), (REASON_SINGLE_LANGUAGE,))
    segment_payloads = tuple(
        {"language": language, "blocks": [block.to_dict() for block in segment_blocks]}
        for language, segment_blocks in segments
    )
    return BilingualSplit(changed=True, segments=segment_payloads, reasons=())
