"""Shared rendering helpers for human-readable formats."""

from __future__ import annotations

from ..models import Content


def content_to_markup(content: Content | None) -> str:
    if content is None:
        return ""
    parts: list[str] = []
    for block in content.blocks:
        if block.type == "text":
            parts.append(block.text or "")
        elif block.type == "math":
            delimiter = "$$" if block.metadata.get("display") else "$"
            parts.append(f"{delimiter}{block.latex or ''}{delimiter}")
        elif block.type == "image":
            parts.append(f"![{block.alt_text or 'image'}](asset:{block.asset_id or ''})")
        elif block.type == "code":
            parts.append(f"`{block.text or ''}`")
        elif block.type == "table":
            parts.append("\n" + "\n".join(" | ".join(row) for row in (block.rows or [])) + "\n")
        elif block.type == "line_break":
            parts.append("\n")
    return "".join(parts).strip()


def markup_to_content(value: str) -> Content:
    """Parse inline math and asset markers without interpreting arbitrary Markdown."""
    import re

    pattern = re.compile(
        r"(!\[(?P<alt>[^]]*)\]\(asset:(?P<asset>[^)]+)\)|\$\$(?P<display>.+?)\$\$|\$(?P<inline>.+?)\$)",
        re.DOTALL,
    )
    blocks = []
    from ..models import ContentBlock

    cursor = 0
    for match in pattern.finditer(value):
        if match.start() > cursor:
            blocks.append(ContentBlock(type="text", text=value[cursor : match.start()]))
        if match.group("asset") is not None:
            blocks.append(
                ContentBlock(
                    type="image", asset_id=match.group("asset"), alt_text=match.group("alt")
                )
            )
        elif match.group("display") is not None:
            blocks.append(
                ContentBlock(type="math", latex=match.group("display"), metadata={"display": True})
            )
        else:
            blocks.append(ContentBlock(type="math", latex=match.group("inline")))
        cursor = match.end()
    if cursor < len(value):
        blocks.append(ContentBlock(type="text", text=value[cursor:]))
    return Content(blocks)
