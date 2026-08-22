"""Review-first import bundles shared by browser and coding workflows."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from .exceptions import ImportBundleError
from .models import SCHEMA_VERSION, QuestionSet
from .validation import validate_with_schema

BUNDLE_VERSION = "1.0"
SESSION_VERSION = "1.0"
_MAX_JSON_BYTES = 2 * 1024 * 1024
_MAX_SOURCE_BYTES = 5 * 1024 * 1024
_QUESTION_FIELDS = {
    "id",
    "type",
    "language",
    "subject",
    "stem",
    "choices",
    "answer",
    "solution",
    "hints",
    "assets",
    "tags",
    "difficulty",
    "source",
    "taxonomy",
    "subquestions",
    "metadata",
}
_EVIDENCE_FIELDS = {
    "stem",
    "choices",
    "answer",
    "solution",
    "subject",
    "source",
    "metadata",
}
_PROPOSAL_FIELDS = {
    "stem",
    "choices",
    "answer",
    "solution",
    "subject",
    "tags",
    "difficulty",
    "metadata",
}
_TRANSFORMS = {
    "identity",
    "content",
    "choices",
    "choice_answer",
    "text_answer",
    "string_list",
    "number",
    "mapping",
}


@dataclass(frozen=True, slots=True)
class ImportCase:
    """Discoverable metadata for one bundled, synthetic import workflow."""

    id: str
    title: str
    route: str
    source_type: str
    summary: str
    has_ai_proposal: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ImportCase:
        return cls(
            id=str(payload["id"]),
            title=str(payload["title"]),
            route=str(payload["route"]),
            source_type=str(payload["source_type"]),
            summary=str(payload["summary"]),
            has_ai_proposal=bool(payload.get("has_ai_proposal", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "route": self.route,
            "source_type": self.source_type,
            "summary": self.summary,
            "has_ai_proposal": self.has_ai_proposal,
        }


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _resource_root() -> Any:
    return files("dq_questionbank").joinpath("data", "import_cases")


def _load_resource_json(resource: Any, *, label: str) -> Any:
    try:
        raw = resource.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise ImportBundleError(f"Missing {label}.") from exc
    if len(raw) > _MAX_JSON_BYTES:
        raise ImportBundleError(f"{label} exceeds the 2 MiB JSON limit.")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportBundleError(f"{label} must be valid UTF-8 JSON.") from exc


def list_import_cases() -> tuple[ImportCase, ...]:
    """Return bundled import workflows in deterministic display order."""
    payload = _load_resource_json(_resource_root().joinpath("index.json"), label="case index")
    if not isinstance(payload, list):
        raise ImportBundleError("The case index must be a JSON array.")
    cases = tuple(ImportCase.from_dict(item) for item in payload)
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ImportBundleError("The case index contains duplicate identifiers.")
    return cases


def get_import_case(case_id: str) -> ImportCase:
    """Find one bundled import workflow without guessing aliases."""
    matches = [case for case in list_import_cases() if case.id == case_id]
    if not matches:
        available = ", ".join(case.id for case in list_import_cases())
        raise ImportBundleError(f"Unknown import case {case_id!r}. Available: {available}.")
    return matches[0]


def _safe_relative_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ImportBundleError("Bundle file paths must be non-empty strings.")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ImportBundleError(f"Unsafe bundle path: {value!r}.")
    if any(not part for part in path.parts):
        raise ImportBundleError(f"Unsafe bundle path: {value!r}.")
    return path


def _join_bundle(root: Any, relative: PurePosixPath) -> Any:
    target = root.joinpath(*relative.parts)
    if isinstance(root, Path):
        resolved_root = root.resolve()
        try:
            resolved_target = target.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ImportBundleError(f"Missing bundle file: {relative.as_posix()}.") from exc
        if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
            raise ImportBundleError(f"Bundle path escapes its root: {relative.as_posix()}.")
        if target.is_symlink():
            raise ImportBundleError(f"Bundle files must not be symbolic links: {relative.as_posix()}.")
    return target


def _read_reference(root: Any, reference: Any, *, label: str, json_file: bool) -> Any:
    if not isinstance(reference, dict):
        raise ImportBundleError(f"{label} reference must be an object.")
    relative = _safe_relative_path(reference.get("path"))
    expected = reference.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ImportBundleError(f"{label} reference requires a SHA-256 digest.")
    target = _join_bundle(root, relative)
    try:
        raw = target.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise ImportBundleError(f"Unable to read {label}: {relative.as_posix()}.") from exc
    limit = _MAX_JSON_BYTES if json_file else _MAX_SOURCE_BYTES
    if len(raw) > limit:
        raise ImportBundleError(f"{label} exceeds its {limit // (1024 * 1024)} MiB limit.")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ImportBundleError(f"{label} digest does not match {relative.as_posix()}.")
    if not json_file:
        return raw
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportBundleError(f"{label} must be valid UTF-8 JSON.") from exc


def _leaf_paths(value: Any, prefix: str = "") -> set[str]:
    if isinstance(value, dict):
        result: set[str] = set()
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(_leaf_paths(item, path))
        return result
    return {prefix} if prefix else set()


def _lookup(record: dict[str, Any], path: str) -> Any:
    current: Any = record
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(path)
        current = current[segment]
    return current


def _content(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"blocks": [{"type": "text", "text": value}]}
    if isinstance(value, dict) and isinstance(value.get("blocks"), list):
        return copy.deepcopy(value)
    raise ImportBundleError("Content mappings require a string or canonical blocks object.")


def _choices(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ImportBundleError("Choice mappings require an array.")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ImportBundleError(f"Choice {index} must be an object.")
        choice_id = item.get("id")
        if not isinstance(choice_id, str) or not choice_id:
            raise ImportBundleError(f"Choice {index} requires a non-empty id.")
        raw_content = item.get("content", item.get("text"))
        result.append({"id": choice_id, "content": _content(raw_content)})
    return result


def _transform(value: Any, transform: str) -> Any:
    if transform not in _TRANSFORMS:
        raise ImportBundleError(f"Unsupported mapping transform: {transform!r}.")
    if transform == "identity":
        return copy.deepcopy(value)
    if transform == "content":
        return _content(value)
    if transform == "choices":
        return _choices(value)
    if transform == "choice_answer":
        return {"kind": "choice", "value": str(value)}
    if transform == "text_answer":
        return {"kind": "text", "value": copy.deepcopy(value)}
    if transform == "string_list":
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item) for item in value]
        raise ImportBundleError("String-list mappings require a string or array.")
    if transform == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ImportBundleError("Number mappings require a JSON number.")
        return value
    if transform == "mapping":
        if not isinstance(value, dict):
            raise ImportBundleError("Mapping transforms require an object.")
        return copy.deepcopy(value)
    raise AssertionError(transform)


def _map_records(manifest: dict[str, Any], records_payload: Any) -> tuple[QuestionSet, list[dict]]:
    records = records_payload.get("records") if isinstance(records_payload, dict) else None
    if not isinstance(records, list) or not records:
        raise ImportBundleError("The records file must contain a non-empty records array.")
    mapping = manifest.get("mapping")
    defaults = manifest.get("defaults", {})
    ignored = set(manifest.get("ignore_paths", []))
    if not isinstance(mapping, dict) or not isinstance(defaults, dict):
        raise ImportBundleError("Bundle mapping and defaults must be objects.")
    if not all(target in _QUESTION_FIELDS for target in mapping):
        raise ImportBundleError("Bundle mapping contains an unsupported canonical field.")

    questions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    mapped_paths: set[str] = set()
    for target, rule in mapping.items():
        if not isinstance(rule, dict) or not isinstance(rule.get("path"), str):
            raise ImportBundleError(f"Mapping for {target!r} requires a source path.")
        mapped_paths.add(rule["path"])

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ImportBundleError(f"Source record {index} must be an object.")
        question: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            **copy.deepcopy(defaults),
        }
        for target, rule in mapping.items():
            path = rule["path"]
            try:
                value = _lookup(record, path)
            except KeyError:
                if rule.get("required", False):
                    raise ImportBundleError(
                        f"Source record {index} is missing required field {path!r}."
                    ) from None
                continue
            question[target] = _transform(value, str(rule.get("transform", "identity")))
        if "id" not in question:
            raise ImportBundleError(f"Source record {index} did not map a question id.")
        question_id = str(question["id"])
        question["id"] = question_id
        questions.append(question)
        for path in sorted(_leaf_paths(record) - mapped_paths - ignored):
            if any(path.startswith(f"{ignored_path}.") for ignored_path in ignored):
                continue
            diagnostics.append(
                {
                    "question_id": question_id,
                    "path": path,
                    "code": "unmapped_source_field",
                    "severity": "warning",
                    "message": "Source content was not mapped and remains available for review.",
                }
            )

    template = manifest.get("question_set")
    if not isinstance(template, dict):
        raise ImportBundleError("Bundle question_set must be an object.")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "id": template.get("id", manifest.get("id", "imported")),
        "title": template.get("title", manifest.get("title", "Imported questions")),
        "language": template.get("language", "en"),
        "questions": questions,
    }
    for key in ("description", "metadata"):
        if key in template:
            payload[key] = copy.deepcopy(template[key])
    issues = validate_with_schema(payload)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        first = errors[0]
        raise ImportBundleError(f"Mapped candidate is invalid at {first.path}: {first.message}")
    diagnostics.extend(issue.to_dict() for issue in issues if issue.severity != "error")
    return QuestionSet.from_dict(payload), diagnostics


def _validate_evidence(
    manifest: dict[str, Any], question_set: QuestionSet, evidence_payload: Any
) -> dict[str, list[dict[str, Any]]]:
    evidence = evidence_payload.get("evidence") if isinstance(evidence_payload, dict) else None
    if not isinstance(evidence, list):
        raise ImportBundleError("The evidence file must contain an evidence array.")
    question_ids = {question.id for question in question_set.questions}
    source_path = manifest["source"]["path"]
    grouped = {question_id: [] for question_id in question_ids}
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise ImportBundleError(f"Evidence record {index} must be an object.")
        question_id = item.get("question_id")
        field = item.get("field")
        excerpt = item.get("excerpt")
        if question_id not in question_ids:
            raise ImportBundleError(f"Evidence record {index} references an unknown question.")
        if field not in _EVIDENCE_FIELDS:
            raise ImportBundleError(f"Evidence record {index} references an unsupported field.")
        if item.get("source_path") != source_path:
            raise ImportBundleError(f"Evidence record {index} is not bound to the declared source.")
        if not isinstance(item.get("locator"), str) or not item["locator"]:
            raise ImportBundleError(f"Evidence record {index} requires a locator.")
        if not isinstance(excerpt, str) or not excerpt:
            raise ImportBundleError(f"Evidence record {index} requires an excerpt.")
        if item.get("excerpt_sha256") != hashlib.sha256(excerpt.encode("utf-8")).hexdigest():
            raise ImportBundleError(f"Evidence record {index} has a stale excerpt digest.")
        grouped[str(question_id)].append(copy.deepcopy(item))
    required_fields = manifest.get("required_evidence_fields", ["stem"])
    if not isinstance(required_fields, list) or not set(required_fields) <= _EVIDENCE_FIELDS:
        raise ImportBundleError("required_evidence_fields contains an unsupported field.")
    for question_id, items in grouped.items():
        present = {item["field"] for item in items}
        missing = set(required_fields) - present
        if missing:
            raise ImportBundleError(
                f"Question {question_id!r} is missing evidence for: {', '.join(sorted(missing))}."
            )
        items.sort(key=lambda item: (item["field"], item["locator"]))
    return grouped


def _apply_proposal(
    manifest: dict[str, Any], base: QuestionSet, proposal: Any
) -> tuple[QuestionSet, list[dict[str, Any]]]:
    if not isinstance(proposal, dict) or not isinstance(proposal.get("changes"), list):
        raise ImportBundleError("The proposal file must contain a changes array.")
    base_payload = base.to_dict()
    if proposal.get("base_sha256") != _digest(base_payload):
        raise ImportBundleError("The AI proposal is stale for the mapped candidate.")
    allowed = set(manifest.get("allowed_proposal_fields", []))
    if not allowed <= _PROPOSAL_FIELDS:
        raise ImportBundleError("allowed_proposal_fields contains an unsupported field.")
    questions = {question["id"]: question for question in base_payload["questions"]}
    applied: list[dict[str, Any]] = []
    for index, change in enumerate(proposal["changes"]):
        if not isinstance(change, dict):
            raise ImportBundleError(f"Proposal change {index} must be an object.")
        question_id = change.get("question_id")
        field = change.get("field")
        if question_id not in questions:
            raise ImportBundleError(f"Proposal change {index} references an unknown question.")
        if field not in allowed:
            raise ImportBundleError(f"Proposal change {index} crosses its allowed field boundary.")
        if questions[question_id].get(field) != change.get("before"):
            raise ImportBundleError(f"Proposal change {index} has stale before evidence.")
        if not isinstance(change.get("reason"), str) or not change["reason"].strip():
            raise ImportBundleError(f"Proposal change {index} requires a review reason.")
        questions[question_id][field] = copy.deepcopy(change.get("after"))
        applied.append(copy.deepcopy(change))
    issues = validate_with_schema(base_payload)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        first = errors[0]
        raise ImportBundleError(f"AI proposal produces invalid content at {first.path}: {first.message}")
    return QuestionSet.from_dict(base_payload), applied


def _session_digest(session: dict[str, Any]) -> str:
    payload = {key: value for key, value in session.items() if key != "session_sha256"}
    return _digest(payload)


def _verify_session(session: Any) -> dict[str, Any]:
    if not isinstance(session, dict) or session.get("session_version") != SESSION_VERSION:
        raise ImportBundleError("Unsupported candidate-session document.")
    if session.get("session_sha256") != _session_digest(session):
        raise ImportBundleError("Candidate-session digest is stale.")
    if not isinstance(session.get("candidates"), list):
        raise ImportBundleError("Candidate session requires a candidates array.")
    return session


def _read_manifest(root: Any) -> dict[str, Any]:
    manifest_path = _join_bundle(root, PurePosixPath("bundle.json"))
    manifest = _load_resource_json(manifest_path, label="bundle manifest")
    if not isinstance(manifest, dict) or manifest.get("bundle_version") != BUNDLE_VERSION:
        raise ImportBundleError("Unsupported import bundle version.")
    for key in ("id", "title", "route", "source", "records", "evidence"):
        if key not in manifest:
            raise ImportBundleError(f"Bundle manifest is missing {key!r}.")
    return manifest


def _prepare_root(root: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _read_manifest(root)
    _read_reference(root, manifest["source"], label="source file", json_file=False)
    records = _read_reference(root, manifest["records"], label="records file", json_file=True)
    evidence = _read_reference(root, manifest["evidence"], label="evidence file", json_file=True)
    base, diagnostics = _map_records(manifest, records)
    grouped_evidence = _validate_evidence(manifest, base, evidence)
    candidate = base
    applied_changes: list[dict[str, Any]] = []
    if manifest.get("proposal") is not None:
        proposal = _read_reference(
            root, manifest["proposal"], label="AI proposal file", json_file=True
        )
        candidate, applied_changes = _apply_proposal(manifest, base, proposal)
    candidate_by_id = {item.id: item.to_dict() for item in candidate.questions}
    base_by_id = {item.id: item.to_dict() for item in base.questions}
    candidates = []
    for question_id in sorted(candidate_by_id):
        candidates.append(
            {
                "question_id": question_id,
                "status": "candidate_ready",
                "decision": "pending",
                "revision": 1,
                "base_question": base_by_id[question_id],
                "question": candidate_by_id[question_id],
                "question_sha256": _digest(candidate_by_id[question_id]),
                "evidence": grouped_evidence[question_id],
                "diagnostics": [
                    item for item in diagnostics if item.get("question_id") in {None, question_id}
                ],
            }
        )
    template = candidate.to_dict()
    template["questions"] = []
    session = {
        "session_version": SESSION_VERSION,
        "bundle_id": manifest["id"],
        "bundle_title": manifest["title"],
        "route": manifest["route"],
        "parser": {
            "identity": str(manifest.get("parser") or "canonical-records/1"),
            "route": str(manifest["route"]),
        },
        "source": copy.deepcopy(manifest["source"]),
        "status": "candidate_ready",
        "question_set_template": template,
        "proposal": {
            "applied": bool(applied_changes),
            "changes": applied_changes,
            "requires_human_review": True,
        },
        "candidates": candidates,
    }
    session["session_sha256"] = _session_digest(session)
    return session, manifest


def prepare_import_bundle(bundle: str | Path) -> dict[str, Any]:
    """Map one bundle into a digest-bound candidate session without persistence."""
    path = Path(bundle).expanduser()
    root = path if path.is_dir() else path.parent
    if path.is_file() and path.name != "bundle.json":
        raise ImportBundleError("A bundle file must be named bundle.json.")
    if not root.is_dir() or root.is_symlink():
        raise ImportBundleError("Import bundle root must be a regular directory.")
    session, _ = _prepare_root(root.resolve())
    return session


def prepare_import_case(case_id: str) -> dict[str, Any]:
    """Prepare one installed synthetic case through the same public boundary."""
    case = get_import_case(case_id)
    root = _resource_root().joinpath(case.id)
    session, _ = _prepare_root(root)
    return session


def review_import_session(
    session: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    """Apply explicit, digest-bound human accept/reject decisions."""
    reviewed = copy.deepcopy(_verify_session(session))
    entries = decisions.get("decisions") if isinstance(decisions, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ImportBundleError("Review decisions must contain a non-empty decisions array.")
    by_id = {candidate["question_id"]: candidate for candidate in reviewed["candidates"]}
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ImportBundleError(f"Review decision {index} must be an object.")
        question_id = entry.get("question_id")
        if question_id not in by_id or question_id in seen:
            raise ImportBundleError(f"Review decision {index} has an unknown or duplicate question.")
        seen.add(str(question_id))
        candidate = by_id[question_id]
        if (
            candidate.get("decision") != "pending"
            or candidate.get("status") != "candidate_ready"
        ):
            raise ImportBundleError(f"Review decision {index} targets an already reviewed candidate.")
        if entry.get("candidate_sha256") != candidate["question_sha256"]:
            raise ImportBundleError(f"Review decision {index} is stale for its candidate.")
        decision = entry.get("decision")
        if decision not in {"accepted", "rejected"}:
            raise ImportBundleError(f"Review decision {index} must accept or reject the candidate.")
        edited = entry.get("edited_question")
        if edited is not None:
            if decision != "accepted" or not isinstance(edited, dict):
                raise ImportBundleError("Only accepted candidates may include a reviewed edit.")
            if edited.get("id") != question_id:
                raise ImportBundleError("A reviewed edit must retain the candidate question id.")
            probe = copy.deepcopy(reviewed["question_set_template"])
            probe["questions"] = [edited]
            errors = [issue for issue in validate_with_schema(probe) if issue.severity == "error"]
            if errors:
                raise ImportBundleError(
                    f"Reviewed edit is invalid at {errors[0].path}: {errors[0].message}"
                )
            candidate["question"] = copy.deepcopy(edited)
            candidate["question_sha256"] = _digest(edited)
            candidate["revision"] = int(candidate.get("revision", 1)) + 1
        candidate["decision"] = decision
        candidate["status"] = "reviewed"
        candidate["review_note"] = str(entry.get("note", ""))
    pending = [item for item in reviewed["candidates"] if item["decision"] == "pending"]
    reviewed["status"] = "in_review" if pending else "reviewed"
    reviewed["session_sha256"] = _session_digest(reviewed)
    return reviewed


def export_reviewed_questions(session: dict[str, Any]) -> QuestionSet:
    """Export accepted candidates; never save them to an application store."""
    verified = _verify_session(session)
    if verified.get("status") != "reviewed":
        raise ImportBundleError("Every candidate requires an explicit review decision before export.")
    payload = copy.deepcopy(verified["question_set_template"])
    payload["questions"] = [
        copy.deepcopy(item["question"])
        for item in verified["candidates"]
        if item["decision"] == "accepted"
    ]
    errors = [issue for issue in validate_with_schema(payload) if issue.severity == "error"]
    if errors:
        raise ImportBundleError(f"Reviewed export is invalid at {errors[0].path}: {errors[0].message}")
    return QuestionSet.from_dict(payload)


def _write_json_atomic(target: Path, payload: Any) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink() or target.is_symlink():
        raise ImportBundleError("Refusing to write import output through a symbolic link.")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def run_import_case(case_id: str, output_dir: str | Path) -> dict[str, str]:
    """Replay a bundled review case and write its three inspectable artifacts."""
    case = get_import_case(case_id)
    root = _resource_root().joinpath(case.id)
    session, manifest = _prepare_root(root)
    if not isinstance(manifest.get("decisions"), dict):
        raise ImportBundleError("Runnable cases require a reviewed decisions file.")
    decisions = _read_reference(
        root, manifest["decisions"], label="review decisions", json_file=True
    )
    reviewed = review_import_session(session, decisions)
    question_set = export_reviewed_questions(reviewed)
    destination = Path(output_dir).expanduser()
    if destination.is_symlink():
        raise ImportBundleError("Import case output directory must not be a symbolic link.")
    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve()
    if destination.is_symlink():
        raise ImportBundleError("Import case output directory must not be a symbolic link.")
    paths = {
        "candidate_session": destination / f"{case.id}.candidate-session.json",
        "reviewed_session": destination / f"{case.id}.reviewed-session.json",
        "question_set": destination / f"{case.id}.question-set.json",
    }
    _write_json_atomic(paths["candidate_session"], session)
    _write_json_atomic(paths["reviewed_session"], reviewed)
    _write_json_atomic(paths["question_set"], question_set.to_dict())
    return {key: str(value) for key, value in paths.items()}
