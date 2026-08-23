"""Split a synthetic vector PDF into per-question chunks.

PDF is the hardest import source: real papers arrive as opaque binary blobs.
This module turns a synthetic vector PDF - the repo's deterministic,
library-free format from ``scripts/build_import_cases.py`` - into ordered
per-question text chunks at deterministic boundaries, so the rest of the
toolchain (worksets, transcription skeletons) works on auditable data.

The extraction is deliberately minimal: it reads uncompressed latin-1
content streams, walks the ``(text) Tj T*`` line pattern, and tracks page
numbers. It never decompresses, never renders, and never guesses - a PDF
whose streams do not follow the synthetic pattern yields no chunks and a
machine-readable reason instead of half-parsed output. Part of #89.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PDF_SPLIT_VERSION = "pdf-split/1"

REASON_NO_MARKERS = "no-question-markers"
REASON_EMPTY_PDF = "empty-pdf"
REASON_NO_TEXT_LINES = "no-text-lines"

_SPLIT_FIELDS = {"chunks", "header_lines", "reasons", "version"}
_LINE_FIELDS = {"page", "index", "text"}
_CHUNK_FIELDS = {"question_key", "marker_text", "lines"}

_PAGE_OBJECT_RE = re.compile(
    rb"<<\s*/Type\s*/Page\b.*?/Contents\s+(\d+)\s+0\s+R",
    re.DOTALL,
)
_STREAM_OBJECT_RE = re.compile(
    rb"(\d+)\s+0\s+obj\s*<<\s*/Length\s+\d+\s+>>\s*stream\n(.*?)\nendstream",
    re.DOTALL,
)
_TEXT_LINE_RE = re.compile(r"\((.*?)\)\s+Tj\s+T\*")
_PDF_ESCAPES = {"\\(": "(", "\\)": ")", "\\\\": "\\"}


@dataclass(frozen=True, slots=True)
class PdfTextLine:
    """One extracted text line with its page and in-page index."""

    page: int
    index: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"page": self.page, "index": self.index, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfTextLine:
        unknown = sorted(set(data) - _LINE_FIELDS)
        if unknown:
            raise ValueError(f"Unknown pdf-line field(s): {', '.join(unknown)}.")
        return cls(page=int(data["page"]), index=int(data["index"]), text=str(data["text"]))


def _unescape(match: re.Match[str]) -> str:
    text = match.group(1)
    for escaped, plain in _PDF_ESCAPES.items():
        text = text.replace(escaped, plain)
    return text


def _extract_page_streams(pdf_bytes: bytes) -> list[tuple[int, bytes]]:
    """Pair each page object number with its decoded content stream."""
    streams = {
        int(number): body
        for number, body in _STREAM_OBJECT_RE.findall(pdf_bytes)
    }
    pages: list[tuple[int, bytes]] = []
    seen: set[int] = set()
    for match in _PAGE_OBJECT_RE.finditer(pdf_bytes):
        contents_id = int(match.group(1))
        if contents_id in streams and contents_id not in seen:
            seen.add(contents_id)
            pages.append((len(pages) + 1, streams[contents_id]))
    return pages


def extract_text_lines(pdf_bytes: bytes) -> tuple[PdfTextLine, ...]:
    """Extract every ``(text) Tj T*`` line, page by page, in order (pure)."""
    lines: list[PdfTextLine] = []
    for page_number, stream in _extract_page_streams(pdf_bytes):
        text = stream.decode("latin-1", errors="replace")
        for index, match in enumerate(_TEXT_LINE_RE.finditer(text)):
            lines.append(PdfTextLine(page=page_number, index=index, text=_unescape(match)))
    return tuple(lines)



@dataclass(frozen=True, slots=True)
class PdfChunk:
    """One per-question chunk: from a marker line up to the next marker."""

    question_key: str
    marker_text: str
    lines: tuple[PdfTextLine, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_key": self.question_key,
            "marker_text": self.marker_text,
            "lines": [line.to_dict() for line in self.lines],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfChunk:
        unknown = sorted(set(data) - _CHUNK_FIELDS)
        if unknown:
            raise ValueError(f"Unknown pdf-chunk field(s): {', '.join(unknown)}.")
        return cls(
            question_key=str(data["question_key"]),
            marker_text=str(data["marker_text"]),
            lines=tuple(PdfTextLine.from_dict(item) for item in data["lines"]),
        )


@dataclass(frozen=True, slots=True)
class PdfSplitResult:
    """The outcome of splitting one PDF at question markers.

    ``chunks`` is empty when no marker matches, in which case ``reasons``
    carries exactly one canonical reason. ``header_lines`` holds any leading
    lines before the first marker (titles, instructions).
    """

    chunks: tuple[PdfChunk, ...]
    header_lines: tuple[PdfTextLine, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PDF_SPLIT_VERSION,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "header_lines": [line.to_dict() for line in self.header_lines],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfSplitResult:
        unknown = sorted(set(data) - _SPLIT_FIELDS)
        if unknown:
            raise ValueError(f"Unknown pdf-split field(s): {', '.join(unknown)}.")
        if str(data.get("version", PDF_SPLIT_VERSION)) != PDF_SPLIT_VERSION:
            raise ValueError(f"Unsupported pdf-split version: {data['version']!r}.")
        return cls(
            chunks=tuple(PdfChunk.from_dict(item) for item in data["chunks"]),
            header_lines=tuple(
                PdfTextLine.from_dict(item) for item in data["header_lines"]
            ),
            reasons=tuple(str(item) for item in data["reasons"]),
        )


def _marker_key(marker_pattern: re.Pattern[str], text: str) -> str | None:
    """Return the question key when the line STARTS with a marker."""
    match = marker_pattern.match(text)
    if match is None:
        return None
    key = match.group(1) if match.groups() else match.group(0)
    return key.strip()


def split_pdf_questions(
    pdf_bytes: bytes, marker_pattern: str = r"Question ([A-Z]+-\d+)"
) -> PdfSplitResult:
    """Split one synthetic PDF into per-question chunks (pure, deterministic).

    A chunk starts at each text line that STARTS with ``marker_pattern``
    (one capture group naming the question key) and runs to the next marker
    line or the end of the document, across pages. Mid-sentence references
    never split because only line starts match. The same bytes and pattern
    always produce the same chunks; a PDF with no text or no markers is
    returned with exactly one canonical reason.
    """
    if not pdf_bytes.strip():
        return PdfSplitResult((), (), (REASON_EMPTY_PDF,))
    lines = extract_text_lines(pdf_bytes)
    if not lines:
        return PdfSplitResult((), (), (REASON_NO_TEXT_LINES,))
    pattern = re.compile(marker_pattern)
    chunks: list[PdfChunk] = []
    header: list[PdfTextLine] = []
    key: str | None = None
    marker_text = ""
    body: list[PdfTextLine] = []
    for line in lines:
        line_key = _marker_key(pattern, line.text)
        if line_key is not None:
            if key is not None:
                chunks.append(PdfChunk(key, marker_text, tuple(body)))
            key = line_key
            marker_text = line.text
            body = [line]
        elif key is None:
            header.append(line)
        else:
            body.append(line)
    if key is not None:
        chunks.append(PdfChunk(key, marker_text, tuple(body)))
    if not chunks:
        return PdfSplitResult((), tuple(header), (REASON_NO_MARKERS,))
    return PdfSplitResult(chunks=tuple(chunks), header_lines=tuple(header), reasons=())
