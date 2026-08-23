"""Import native Word math (OMML) from a DOCX into LaTeX sources.

The Word publishing path exports canonical LaTeX; this module is the
import direction. It reads ``m:oMath`` / ``m:oMathPara`` elements from a
DOCX's ``word/document.xml`` using only the standard library and maps
them to deterministic LaTeX:

- fractions, sub/superscripts and sub+sup pairs;
- square and n-th roots;
- delimiters (with custom begin/end characters);
- named functions (``m:func``) mapped to standard LaTeX commands;
- n-ary operators (sums, integrals, products) with their bounds;
- plain runs, including unicode symbols.

Constructs with no deterministic LaTeX form are **not guessed**: their
text content is preserved and the construct name is reported on
``unsupported`` so a caller can surface a manual-review finding.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = f"{{{M_NS}}}"
W = f"{{{W_NS}}}"

_FUNCTION_COMMANDS = {
    "sin": "\\sin",
    "cos": "\\cos",
    "tan": "\\tan",
    "cot": "\\cot",
    "sec": "\\sec",
    "csc": "\\csc",
    "arcsin": "\\arcsin",
    "arccos": "\\arccos",
    "arctan": "\\arctan",
    "sinh": "\\sinh",
    "cosh": "\\cosh",
    "tanh": "\\tanh",
    "ln": "\\ln",
    "log": "\\log",
    "lim": "\\lim",
    "min": "\\min",
    "max": "\\max",
    "exp": "\\exp",
    "det": "\\det",
}

_NARY_COMMANDS = {
    "∑": "\\sum",
    "∫": "\\int",
    "∏": "\\prod",
    "∬": "\\iint",
    "∭": "\\iiint",
    "∮": "\\oint",
}


@dataclass(frozen=True, slots=True)
class OmmlFormula:
    """One imported formula with its LaTeX source and review notes."""

    latex: str
    display: bool
    unsupported: tuple[str, ...]


def _direct_child(element: ET.Element, tag: str) -> ET.Element | None:
    return next((child for child in element if child.tag == tag), None)


def _direct_children(element: ET.Element, tag: str) -> list[ET.Element]:
    return [child for child in element if child.tag == tag]


def _text_of(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{M}t"))


class _Converter:
    def __init__(self) -> None:
        self.unsupported: list[str] = []

    def convert(self, element: ET.Element) -> str:
        tag = element.tag
        if tag in (f"{M}oMath", f"{M}oMathPara"):
            return "".join(self.convert(child) for child in element)
        if tag == f"{M}r":
            return _text_of(element)
        if tag == f"{M}f":
            numerator = self._child_latex(element, f"{M}num")
            denominator = self._child_latex(element, f"{M}den")
            return f"\\frac{{{numerator}}}{{{denominator}}}"
        if tag == f"{M}sSup":
            base = self._child_latex(element, f"{M}e")
            power = self._child_latex(element, f"{M}sup")
            return f"{base}^{{{power}}}"
        if tag == f"{M}sSub":
            base = self._child_latex(element, f"{M}e")
            index = self._child_latex(element, f"{M}sub")
            return f"{base}_{{{index}}}"
        if tag == f"{M}sSubSup":
            base = self._child_latex(element, f"{M}e")
            index = self._child_latex(element, f"{M}sub")
            power = self._child_latex(element, f"{M}sup")
            return f"{base}_{{{index}}}^{{{power}}}"
        if tag == f"{M}rad":
            degree = self._child_latex(element, f"{M}deg")
            body = self._child_latex(element, f"{M}e")
            if degree:
                return f"\\sqrt[{degree}]{{{body}}}"
            return f"\\sqrt{{{body}}}"
        if tag == f"{M}d":
            return self._delimiter(element)
        if tag == f"{M}func":
            name = self._child_latex(element, f"{M}fName").strip()
            body = self._child_latex(element, f"{M}e")
            command = _FUNCTION_COMMANDS.get(name)
            if command:
                return f"{command} {body}"
            return f"\\operatorname{{{name}}}\\left({body}\\right)"
        if tag == f"{M}nary":
            return self._nary(element)
        containers = (f"{M}e", f"{M}num", f"{M}den", f"{M}deg", f"{M}sub", f"{M}sup", f"{M}fName")
        if tag in containers:
            return "".join(self.convert(child) for child in element)
        local = tag.split("}", 1)[-1] if "}" in tag else tag
        self.unsupported.append(local)
        return _text_of(element)

    def _child_latex(self, element: ET.Element, tag: str) -> str:
        child = _direct_child(element, tag)
        if child is None:
            return ""
        return self.convert(child)

    def _delimiter(self, element: ET.Element) -> str:
        properties = _direct_child(element, f"{M}dPr")
        begin, end = "(", ")"
        if properties is not None:
            begin_node = _direct_child(properties, f"{M}begChr")
            end_node = _direct_child(properties, f"{M}endChr")
            if begin_node is not None and begin_node.get(f"{M}val"):
                begin = begin_node.get(f"{M}val") or "("
            if end_node is not None and end_node.get(f"{M}val"):
                end = end_node.get(f"{M}val") or ")"
        inner = "".join(
            self.convert(child) for child in _direct_children(element, f"{M}e")
        )
        return f"\\left{begin}{inner}\\right{end}"

    def _nary(self, element: ET.Element) -> str:
        properties = _direct_child(element, f"{M}naryPr")
        symbol = "∫"
        if properties is not None:
            chr_node = _direct_child(properties, f"{M}chr")
            if chr_node is not None and chr_node.get(f"{M}val"):
                symbol = chr_node.get(f"{M}val") or "∫"
        command = _NARY_COMMANDS.get(symbol)
        if command is None:
            self.unsupported.append(f"nary:{symbol}")
            command = symbol
        lower = self._child_latex(element, f"{M}sub")
        upper = self._child_latex(element, f"{M}sup")
        body = self._child_latex(element, f"{M}e")
        bounds = ""
        if lower:
            bounds += f"_{{{lower}}}"
        if upper:
            bounds += f"^{{{upper}}}"
        return f"{command}{bounds} {body}"


def parse_omml_element(element: ET.Element) -> OmmlFormula:
    """Convert one ``m:oMath`` element into a LaTeX formula record."""
    converter = _Converter()
    latex = converter.convert(element)
    return OmmlFormula(
        latex=latex.strip(),
        display=element.tag == f"{M}oMathPara",
        unsupported=tuple(sorted(set(converter.unsupported))),
    )


def read_docx_math(source: Path) -> list[OmmlFormula]:
    """Read every formula from a DOCX in document order.

    ``m:oMathPara`` wrappers mark display formulas; bare ``m:oMath``
    elements are inline. The document part is parsed with the standard
    library only; the file is never executed.
    """
    from dataclasses import replace

    formulas: list[OmmlFormula] = []
    with zipfile.ZipFile(source) as archive:
        with archive.open("word/document.xml") as handle:
            tree = ET.parse(handle)
    root = tree.getroot()
    parent_map = {child: parent for parent in root.iter() for child in parent}
    for math in root.iter(f"{M}oMath"):
        parent = parent_map.get(math)
        display = parent is not None and parent.tag == f"{M}oMathPara"
        formula = parse_omml_element(math)
        formulas.append(replace(formula, display=display))
    return formulas

