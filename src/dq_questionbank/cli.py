"""Command-line interface for DQ QuestionBank Core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .exceptions import (
    FormatDetectionError,
    FormatLoadError,
    FormatWriteError,
    QuestionBankError,
    SchemaNotFoundError,
)
from .registry import default_registry
from .validation import validate_question_set

_FORMAT_CHOICES = ("json", "markdown", "latex", "docx")


class _DeprecatedAction(argparse.Action):
    """Warn on a deprecated flag and forward the value unchanged."""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


def _shared_format_flags(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--input-format",
        dest="input_format",
        choices=_FORMAT_CHOICES,
        help="Override automatic format detection.",
    )
    subparser.add_argument(
        "--from",
        dest="input_format",
        action=_DeprecatedAction,
        choices=_FORMAT_CHOICES,
        help=argparse.SUPPRESS,
    )
    subparser.add_argument(
        "--output-format",
        dest="output_format",
        choices=_FORMAT_CHOICES,
        help="Target format (default: json for import).",
    )
    subparser.add_argument(
        "--to",
        dest="output_format",
        action=_DeprecatedAction,
        choices=_FORMAT_CHOICES,
        help=argparse.SUPPRESS,
    )
    subparser.add_argument(
        "--assets-dir", type=Path, help="Directory for extracted assets."
    )
    subparser.add_argument(
        "--assets-base", type=Path, help="Root path for relative asset URIs."
    )


def _load_source(path, input_format, assets_dir, registry):
    name = input_format or registry.detect_input(path)
    options = {"assets_dir": assets_dir} if assets_dir else {}
    return registry.importer(name).load(path, **options)


def _write_output(question_set, target, output_format, assets_base, registry):
    options = {"assets_base": assets_base} if assets_base else {}
    registry.exporter(output_format).dump(question_set, target, **options)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="dq", description="Work with structured educational questions."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"dq-questionbank-core {__version__}",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    c = commands.add_parser("convert", help="Convert between supported formats.")
    c.add_argument("source", type=Path)
    c.add_argument("-o", "--output", type=Path, required=True)
    _shared_format_flags(c)

    c = commands.add_parser("import", help="Import into canonical JSON.")
    c.add_argument("source", type=Path)
    c.add_argument("-o", "--output", type=Path, required=True)
    _shared_format_flags(c)

    c = commands.add_parser("validate", help="Validate canonical question JSON.")
    c.add_argument("source", type=Path)
    c.add_argument("--json", action="store_true", dest="json_output")

    commands.add_parser("formats", help="List available formats.")

    c = commands.add_parser("serve", help="Open the local playground.")
    c.add_argument("--host", default="127.0.0.1")
    c.add_argument("--port", default=8765, type=int)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        from .web_server import serve as _serve
        _serve(args.host, args.port)
        return 0

    if args.command == "formats":
        registry = default_registry()
        print("Import formats:", ", ".join(registry.import_formats))
        print("Export formats:", ", ".join(registry.export_formats))
        return 0

    if not args.source.is_file():
        print(f"Input file not found: {args.source}", file=sys.stderr)
        return 2

    try:
        registry = default_registry()
        input_format = getattr(args, "input_format", None)
        question_set = _load_source(
            args.source, input_format, getattr(args, "assets_dir", None), registry
        )
        issues = validate_question_set(question_set)

        if args.command == "validate":
            if args.json_output:
                print(
                    json.dumps(
                        [i.to_dict() for i in issues],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            elif issues:
                for issue in issues:
                    print(
                        f"{issue.severity.upper()} {issue.path}: "
                        f"{issue.message} [{issue.code}]"
                    )
            else:
                summary = (
                    f"Valid: {len(question_set.questions)} question(s), "
                    f"schema {question_set.schema_version}."
                )
                print(summary)
            return 1 if any(i.severity == "error" for i in issues) else 0

        output_format = getattr(args, "output_format", None)
        if args.command == "import":
            output_format = "json"
        if output_format is None:
            print(
                "Specify --output-format for convert, or use 'dq import' for JSON.",
                file=sys.stderr,
            )
            return 2

        if issues:
            print("Conversion stopped because validation failed:", file=sys.stderr)
            for issue in issues:
                print(f"- {issue.path}: {issue.message}", file=sys.stderr)
            return 1

        asset_base = getattr(args, "assets_base", None)
        _write_output(question_set, args.output, output_format, asset_base, registry)
        print(f"Wrote {len(question_set.questions)} question(s) to {args.output}.")
        return 0

    except FormatDetectionError as exc:
        print(f"Format error: {exc}", file=sys.stderr)
        return 2
    except FormatLoadError as exc:
        print(f"Load error: {exc}", file=sys.stderr)
        return 2
    except FormatWriteError as exc:
        print(f"Write error: {exc}", file=sys.stderr)
        return 2
    except SchemaNotFoundError as exc:
        print(f"Installation error: {exc}", file=sys.stderr)
        return 2
    except QuestionBankError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())