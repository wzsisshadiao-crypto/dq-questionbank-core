"""Check the declared stable ``dq_questionbank`` Python API against its manifest."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "public-api-manifest.json"
PACKAGE_NAME = "dq_questionbank"

# Methods documented as part of the stable operational surface. Constructors
# and package-level exports are discovered from ``__all__`` automatically.
STABLE_MEMBERS = {
    "Content": ("from_dict", "plain_text", "text", "to_dict"),
    "ContentBlock": ("from_dict", "to_dict"),
    "Asset": ("from_dict", "to_dict"),
    "Choice": ("from_dict", "to_dict"),
    "Answer": ("from_dict", "to_dict"),
    "SourceMetadata": ("from_dict", "to_dict"),
    "TaxonomyRef": ("from_dict", "to_dict"),
    "Question": ("from_dict", "to_dict"),
    "QuestionSet": ("from_dict", "to_dict"),
    "FormatRegistry": (
        "detect_input",
        "export_formats",
        "exporter",
        "import_formats",
        "importer",
        "register_exporter",
        "register_importer",
    ),
    "FilesystemStorageAdapter": ("load", "save"),
}


def _signature(value: Any) -> str:
    signature = inspect.signature(value)
    parameters = [
        parameter.replace(annotation=inspect.Signature.empty)
        for parameter in signature.parameters.values()
    ]
    return str(signature.replace(parameters=parameters, return_annotation=inspect.Signature.empty))


def _describe(value: Any) -> dict[str, str]:
    if isinstance(value, property):
        return {"kind": "property"}
    if inspect.isclass(value):
        return {"kind": "class", "signature": _signature(value)}
    if callable(value):
        return {"kind": "function", "signature": _signature(value)}
    return {"kind": "value", "value": repr(value)}


def build_manifest() -> dict[str, object]:
    package = importlib.import_module(PACKAGE_NAME)
    exports = tuple(package.__all__)
    symbols = {
        name: _describe(getattr(package, name))
        if hasattr(package, name)
        else {"kind": "missing"}
        for name in exports
    }
    members: dict[str, dict[str, str]] = {}
    for class_name, names in STABLE_MEMBERS.items():
        owner = getattr(package, class_name, None)
        for name in names:
            key = f"{class_name}.{name}"
            if owner is None or not hasattr(owner, name):
                members[key] = {"kind": "missing"}
                continue
            descriptor = inspect.getattr_static(owner, name)
            value = descriptor if isinstance(descriptor, property) else getattr(owner, name)
            members[key] = _describe(value)
    return {
        "manifest_version": 1,
        "package": PACKAGE_NAME,
        "exports": list(exports),
        "symbols": symbols,
        "members": members,
    }


def check_manifest(manifest_path: Path = MANIFEST_PATH) -> list[str]:
    try:
        expected = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"Missing public API manifest: {manifest_path}"]
    except json.JSONDecodeError as exc:
        return [f"Invalid public API manifest: {exc}"]
    actual = build_manifest()
    if expected == actual:
        return []
    findings: list[str] = []
    for section in ("exports", "symbols", "members"):
        if expected.get(section) != actual.get(section):
            findings.append(f"Stable public API {section} differ from the manifest.")
    if expected.get("package") != actual["package"]:
        findings.append("Stable public API package differs from the manifest.")
    return findings or ["Stable public API manifest differs."]


def write_manifest(manifest_path: Path = MANIFEST_PATH) -> None:
    manifest_path.write_text(
        json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="Update the checked-in manifest intentionally."
    )
    args = parser.parse_args(argv)
    if args.write:
        write_manifest()
        print(f"Wrote {MANIFEST_PATH.relative_to(ROOT)}")
        return 0
    findings = check_manifest()
    if findings:
        print("Public API compatibility check failed.", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("Stable public API manifest is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
