"""Portable LaTeX export and deterministic import of generated documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..models import QuestionSet
from .common import markup_to_content

BEGIN_MARKER = "% dq-question-set: "
QUESTION_MARKER = "% dq-question: "


def _escape_text(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(character, character) for character in value)


def _render_content(content) -> str:
    output: list[str] = []
    for block in content.blocks:
        if block.type == "text":
            output.append(_escape_text(block.text or ""))
        elif block.type == "math":
            output.append(
                f"\\[{block.latex or ''}\\]"
                if block.metadata.get("display")
                else f"${block.latex or ''}$"
            )
        elif block.type == "image":
            asset_id = _escape_text(block.asset_id or "")
            alt_text = _escape_text(block.alt_text or "image")
            output.append(f"\\dqimage{{{asset_id}}}{{{alt_text}}}")
        elif block.type == "code":
            output.append(r"\texttt{" + _escape_text(block.text or "") + "}")
        elif block.type == "line_break":
            output.append(r"\\")
        elif block.type == "table":
            rows = block.rows or []
            columns = max((len(row) for row in rows), default=1)
            body = " \\\n".join(" & ".join(_escape_text(cell) for cell in row) for row in rows)
            output.append(f"\\begin{{tabular}}{{{'l' * columns}}}\n{body}\n\\end{{tabular}}")
    return "".join(output)


class LatexExporter:
    format_name = "latex"
    extensions = (".tex",)

    def dump(self, question_set: QuestionSet, target: Path, **options: Any) -> None:
        meta = question_set.to_dict()
        meta["questions"] = []
        lines = [
            BEGIN_MARKER + json.dumps(meta, ensure_ascii=False, separators=(",", ":")),
            r"\documentclass{article}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage{amsmath,amssymb,graphicx}",
            r"\newcommand{\dqimage}[2]{\fbox{\textit{Image #1: #2}}}",
            r"\begin{document}",
            f"\\section*{{{_escape_text(question_set.title)}}}",
        ]
        for question in question_set.questions:
            lines.append(
                QUESTION_MARKER
                + json.dumps(question.to_dict(), ensure_ascii=False, separators=(",", ":"))
            )
            lines.append(f"\\subsection*{{Question {_escape_text(question.id)}}}")
            lines.append(_render_content(question.stem))
            if question.choices:
                lines.append(r"\begin{enumerate}")
                for choice in question.choices:
                    lines.append(
                        f"\\item[{_escape_text(choice.id)}.] {_render_content(choice.content)}"
                    )
                lines.append(r"\end{enumerate}")
            if question.solution:
                lines.append(r"\paragraph{Solution} " + _render_content(question.solution))
        lines.append(r"\end{document}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n\n".join(lines) + "\n", encoding="utf-8", newline="\n")


class LatexImporter:
    format_name = "latex"
    extensions = (".tex",)

    def load(self, source: Path, **options: Any) -> QuestionSet:
        text = source.read_text(encoding="utf-8-sig")
        set_meta: dict[str, Any] = {}
        questions: list[dict[str, Any]] = []
        for line in text.splitlines():
            if line.startswith(BEGIN_MARKER):
                set_meta = json.loads(line[len(BEGIN_MARKER) :])
            elif line.startswith(QUESTION_MARKER):
                questions.append(json.loads(line[len(QUESTION_MARKER) :]))
        if questions:
            set_meta["questions"] = questions
            set_meta.setdefault("id", source.stem)
            set_meta.setdefault("title", source.stem)
            return QuestionSet.from_dict(set_meta)
        return self._load_simple_latex(text, source)

    def _load_simple_latex(self, text: str, source: Path) -> QuestionSet:
        """Best-effort import for simple enumerate-based question documents."""
        items = re.findall(r"\\item\s+(.+?)(?=\\item|\\end\{enumerate\})", text, re.DOTALL)
        questions = []
        for index, item in enumerate(items, start=1):
            cleaned = re.sub(r"\\(?:textbf|emph)\{([^}]*)\}", r"\1", item).strip()
            questions.append(
                {
                    "schema_version": "1.0",
                    "id": f"q{index}",
                    "type": "short_answer",
                    "language": "en",
                    "stem": markup_to_content(cleaned).to_dict(),
                }
            )
        return QuestionSet.from_dict(
            {
                "schema_version": "1.0",
                "id": source.stem,
                "title": source.stem,
                "language": "en",
                "questions": questions,
            }
        )
