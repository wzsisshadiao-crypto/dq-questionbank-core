"""Importer and exporter registry with safe built-in defaults."""

from __future__ import annotations

import importlib
import threading
from pathlib import Path

from .exceptions import FormatDetectionError
from .interfaces import QuestionExporter, QuestionImporter


class FormatRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._importers: dict[str, QuestionImporter] = {}
        self._exporters: dict[str, QuestionExporter] = {}

    def register_importer(self, importer: QuestionImporter) -> None:
        if not isinstance(importer, QuestionImporter):
            raise TypeError(
                f"register_importer requires a QuestionImporter, got {type(importer).__name__}"
            )
        with self._lock:
            self._importers[importer.format_name] = importer

    def register_exporter(self, exporter: QuestionExporter) -> None:
        if not isinstance(exporter, QuestionExporter):
            raise TypeError(
                f"register_exporter requires a QuestionExporter, got {type(exporter).__name__}"
            )
        with self._lock:
            self._exporters[exporter.format_name] = exporter

    def importer(self, name: str) -> QuestionImporter:
        with self._lock:
            try:
                return self._importers[name]
            except KeyError as exc:
                raise FormatDetectionError(f"Unsupported input format: {name}") from exc

    def exporter(self, name: str) -> QuestionExporter:
        with self._lock:
            try:
                return self._exporters[name]
            except KeyError as exc:
                raise FormatDetectionError(f"Unsupported output format: {name}") from exc

    def detect_input(self, path: Path) -> str:
        suffix = path.suffix.lower()
        with self._lock:
            for name, importer in self._importers.items():
                if suffix in importer.extensions:
                    return name
        raise FormatDetectionError(f"Cannot detect input format from extension: {suffix or '<none>'}")

    @property
    def import_formats(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._importers))

    @property
    def export_formats(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._exporters))


def default_registry() -> FormatRegistry:
    from .formats.json_format import JsonExporter, JsonImporter
    from .formats.markdown import MarkdownExporter, MarkdownImporter

    registry = FormatRegistry()
    registry.register_importer(JsonImporter())
    registry.register_importer(MarkdownImporter())
    registry.register_exporter(JsonExporter())
    registry.register_exporter(MarkdownExporter())

    for module_name, importer_cls, exporter_cls in (
        ("latex", "LatexImporter", "LatexExporter"),
        ("docx", "DocxImporter", "DocxExporter"),
    ):
        try:
            mod = importlib.import_module(f".formats.{module_name}", package="dq_questionbank")
            registry.register_importer(getattr(mod, importer_cls)())
            registry.register_exporter(getattr(mod, exporter_cls)())
        except ImportError:
            pass
    return registry
