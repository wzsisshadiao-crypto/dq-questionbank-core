"""Importer and exporter registry with safe built-in defaults."""

from __future__ import annotations

from pathlib import Path

from .interfaces import QuestionExporter, QuestionImporter


class FormatRegistry:
    def __init__(self) -> None:
        self._importers: dict[str, QuestionImporter] = {}
        self._exporters: dict[str, QuestionExporter] = {}

    def register_importer(self, importer: QuestionImporter) -> None:
        self._importers[importer.format_name] = importer

    def register_exporter(self, exporter: QuestionExporter) -> None:
        self._exporters[exporter.format_name] = exporter

    def importer(self, name: str) -> QuestionImporter:
        try:
            return self._importers[name]
        except KeyError as exc:
            raise ValueError(f"Unsupported input format: {name}") from exc

    def exporter(self, name: str) -> QuestionExporter:
        try:
            return self._exporters[name]
        except KeyError as exc:
            raise ValueError(f"Unsupported output format: {name}") from exc

    def detect_input(self, path: Path) -> str:
        suffix = path.suffix.lower()
        for name, importer in self._importers.items():
            if suffix in importer.extensions:
                return name
        raise ValueError(f"Cannot detect input format from extension: {suffix or '<none>'}")

    @property
    def import_formats(self) -> tuple[str, ...]:
        return tuple(sorted(self._importers))

    @property
    def export_formats(self) -> tuple[str, ...]:
        return tuple(sorted(self._exporters))


def default_registry() -> FormatRegistry:
    from .formats.docx import DocxExporter, DocxImporter
    from .formats.json_format import JsonExporter, JsonImporter
    from .formats.latex import LatexExporter, LatexImporter
    from .formats.markdown import MarkdownExporter, MarkdownImporter

    registry = FormatRegistry()
    for importer in (JsonImporter(), MarkdownImporter(), LatexImporter(), DocxImporter()):
        registry.register_importer(importer)
    for exporter in (JsonExporter(), MarkdownExporter(), LatexExporter(), DocxExporter()):
        registry.register_exporter(exporter)
    return registry
