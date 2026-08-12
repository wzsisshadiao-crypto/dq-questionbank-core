"""Command-line interface for DQ QuestionBank Core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .registry import default_registry
from .validation import validate_question_set


def _load(path: Path, format_name: str | None, assets_dir: Path | None = None):
    registry = default_registry()
    name = format_name or registry.detect_input(path)
    options = {"assets_dir": assets_dir} if assets_dir else {}
    return registry.importer(name).load(path, **options)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dq", description="Work with structured educational questions."
    )
    parser.add_argument("--version", action="version", version="dq-questionbank-core 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    import_command = commands.add_parser("import", help="Import a document into canonical JSON.")
    import_command.add_argument("source", type=Path)
    import_command.add_argument("-o", "--output", type=Path, required=True)
    import_command.add_argument(
        "--from", dest="input_format", choices=("json", "markdown", "latex", "docx")
    )
    import_command.add_argument("--assets-dir", type=Path)

    validate_command = commands.add_parser("validate", help="Validate canonical question JSON.")
    validate_command.add_argument("source", type=Path)
    validate_command.add_argument("--json", action="store_true", dest="json_output")

    convert_command = commands.add_parser("convert", help="Convert between supported formats.")
    convert_command.add_argument("source", type=Path)
    convert_command.add_argument("-o", "--output", type=Path, required=True)
    convert_command.add_argument(
        "--from", dest="input_format", choices=("json", "markdown", "latex", "docx")
    )
    convert_command.add_argument(
        "--to", dest="output_format", required=True, choices=("json", "markdown", "latex", "docx")
    )
    convert_command.add_argument("--assets-dir", type=Path)
    convert_command.add_argument("--assets-base", type=Path)

    serve_command = commands.add_parser("serve", help="Open the local English-language playground.")
    serve_command.add_argument("--host", default="127.0.0.1")
    serve_command.add_argument("--port", default=8765, type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        from .web_server import serve

        serve(args.host, args.port)
        return 0
    if not args.source.is_file():
        print(f"Input file not found: {args.source}", file=sys.stderr)
        return 2
    try:
        question_set = _load(
            args.source, getattr(args, "input_format", None), getattr(args, "assets_dir", None)
        )
        issues = validate_question_set(question_set)
        if args.command == "validate":
            if args.json_output:
                print(
                    json.dumps([issue.to_dict() for issue in issues], ensure_ascii=False, indent=2)
                )
            elif issues:
                for issue in issues:
                    print(f"{issue.severity.upper()} {issue.path}: {issue.message} [{issue.code}]")
            else:
                summary = (
                    f"Valid: {len(question_set.questions)} question(s), "
                    f"schema {question_set.schema_version}."
                )
                print(summary)
            return 1 if any(issue.severity == "error" for issue in issues) else 0
        if issues:
            print("Conversion stopped because validation failed:", file=sys.stderr)
            for issue in issues:
                print(f"- {issue.path}: {issue.message}", file=sys.stderr)
            return 1
        registry = default_registry()
        output_format = "json" if args.command == "import" else args.output_format
        options = {}
        if getattr(args, "assets_base", None):
            options["assets_base"] = args.assets_base
        registry.exporter(output_format).dump(question_set, args.output, **options)
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
from .exceptions import FormatDetectionError, FormatLoadError, FormatWriteError, QuestionBankError, SchemaNotFoundError
