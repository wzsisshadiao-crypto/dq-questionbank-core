"""Provider-neutral Word publishing helpers.

The module deliberately works with canonical :class:`QuestionSet` values and
JSON requests only.  It does not open a database, execute document macros, or
fetch remote content.  The VBA module shipped under ``examples/word-macro``
is a thin Word UI client for this contract.
"""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import re
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse
from zipfile import ZipFile

from .exceptions import QuestionBankError
from .models import Question, QuestionSet

ENVELOPE_VERSION = "0.2"
SUPPORTED_ENVELOPE_VERSIONS = {"0.1", ENVELOPE_VERSION}
MANAGED_TAG_PREFIX = "dqwb:"
MAX_BRIDGE_REQUEST_BYTES = 8 * 1024 * 1024
SUPPORTED_ROLES = {"stem", "choices", "answer", "analysis", "solution", "hints"}
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class WordPublishingError(QuestionBankError):
    """Raised for invalid publishing contracts or unsafe bridge requests."""


class StaleBlockError(WordPublishingError):
    """Raised when a managed block cannot be refreshed safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def word_macro_source() -> str:
    """Return the VBA module bundled with this package."""

    resource = importlib.resources.files("dq_questionbank").joinpath(
        "data", "word_macro", "DQWordPublishing.bas"
    )
    return resource.read_text(encoding="utf-8")


def question_fingerprint(question: Question | Mapping[str, Any]) -> str:
    payload = question.to_dict() if isinstance(question, Question) else dict(question)
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "http"
        and port is not None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
        and parsed.username is None
        and parsed.password is None
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    )


def validate_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a detached publishing envelope.

    Validation is intentionally strict: the bridge fails closed on policy
    changes so a macro cannot accidentally publish to a remote service.
    """

    if not isinstance(envelope, Mapping):
        raise WordPublishingError("Envelope must be a JSON object.")
    value = json.loads(canonical_json(envelope))
    required = {
        "envelope_version",
        "document_id",
        "mode",
        "service_origin",
        "blocks",
        "refresh",
        "rollback",
        "security",
    }
    missing = sorted(required - set(value))
    if missing:
        raise WordPublishingError(f"Missing envelope field(s): {', '.join(missing)}.")
    if str(value["envelope_version"]) not in SUPPORTED_ENVELOPE_VERSIONS:
        raise WordPublishingError(f"Unsupported envelope version: {value['envelope_version']}.")
    if not isinstance(value["document_id"], str) or not value["document_id"]:
        raise WordPublishingError("document_id must be a non-empty string.")
    if value["mode"] not in {"compose", "final"}:
        raise WordPublishingError("mode must be compose or final.")
    origin = value["service_origin"]
    if not isinstance(origin, str) or not _loopback_origin(origin):
        raise WordPublishingError("service_origin must be an explicit HTTP loopback origin.")
    blocks = value["blocks"]
    if not isinstance(blocks, list):
        raise WordPublishingError("blocks must be an ordered array.")
    seen: set[str] = set()
    for index, block in enumerate(blocks):
        if not isinstance(block, Mapping):
            raise WordPublishingError(f"blocks[{index}] must be an object.")
        for field in ("block_id", "question_id", "question_fingerprint", "roles", "display"):
            if field not in block:
                raise WordPublishingError(f"blocks[{index}] is missing {field}.")
        block_id = block["block_id"]
        if not isinstance(block_id, str) or not block_id or "|" in block_id or block_id in seen:
            raise WordPublishingError(f"Duplicate or empty block_id: {block_id!r}.")
        seen.add(block_id)
        question_id = block["question_id"]
        if not isinstance(question_id, str) or not question_id or "|" in question_id:
            raise WordPublishingError(f"Invalid question_id for {block_id}.")
        fingerprint = str(block["question_fingerprint"])
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint):
            raise WordPublishingError(f"Invalid question fingerprint for {block_id}.")
        valid_roles = bool(block["roles"]) and isinstance(block["roles"], list) and all(
            isinstance(role, str) and role in SUPPORTED_ROLES for role in block["roles"]
        )
        if not valid_roles:
            raise WordPublishingError(f"roles must be a non-empty string array for {block_id}.")
        if not isinstance(block["display"], Mapping):
            raise WordPublishingError(f"display must be an object for {block_id}.")
    refresh = value["refresh"]
    if not isinstance(refresh, Mapping) or refresh.get("strategy") != "explicit":
        raise WordPublishingError("refresh.strategy must be explicit.")
    if refresh.get("on_missing") != "stale" or refresh.get("on_revision_mismatch") != "stale":
        raise WordPublishingError("Missing and revision mismatch policies must be stale.")
    rollback = value["rollback"]
    valid_rollback = (
        isinstance(rollback, Mapping)
        and rollback.get("scope") == "single-block"
        and rollback.get("on_failure") == "restore-previous-block"
    )
    if not valid_rollback:
        raise WordPublishingError("Only single-block restore-previous-block rollback is supported.")
    security = value["security"]
    valid_security = (
        isinstance(security, Mapping)
        and security.get("remote_origins") == []
        and security.get("credentials") == "never"
    )
    if not valid_security:
        raise WordPublishingError("Remote origins must be empty and credentials must be never.")
    if security.get("allowed_origins") != [origin]:
        raise WordPublishingError("security.allowed_origins must contain only service_origin.")
    return value


def build_envelope(
    question_set: QuestionSet,
    question_ids: list[str] | None = None,
    *,
    document_id: str | None = None,
    service_origin: str = "http://127.0.0.1:8766",
    mode: str = "compose",
    roles: list[str] | None = None,
) -> dict[str, Any]:
    """Create a deterministic envelope for reviewed canonical questions."""

    selected = question_ids or [question.id for question in question_set.questions]
    by_id = {question.id: question for question in question_set.questions}
    selected_questions: list[Question] = []
    for question_id in selected:
        if question_id not in by_id:
            raise WordPublishingError(f"Question not found: {question_id}")
        selected_questions.append(by_id[question_id])
    blocks = []
    for index, question in enumerate(selected_questions, 1):
        block_id = f"block-{question.id}-{index:03d}"
        blocks.append(
            {
                "block_id": block_id,
                "question_id": question.id,
                "question_fingerprint": question_fingerprint(question),
                "roles": roles or ["stem", "choices", "answer", "solution"],
                "display": {
                    "show_border": mode == "compose",
                    "math": "native-when-supported",
                    "tables": "preserve-structure",
                },
            }
        )
    envelope = {
        "envelope_version": ENVELOPE_VERSION,
        "document_id": document_id or f"dqwb-{question_set.id}",
        "mode": mode,
        "service_origin": service_origin,
        "blocks": blocks,
        "refresh": {"strategy": "explicit", "on_missing": "stale", "on_revision_mismatch": "stale"},
        "rollback": {"scope": "single-block", "on_failure": "restore-previous-block"},
        "security": {"allowed_origins": [service_origin], "remote_origins": [], "credentials": "never"},
    }
    return validate_envelope(envelope)


def _content_lines(question: Question, roles: list[str]) -> list[str]:
    lines: list[str] = []
    if "stem" in roles:
        lines.append(f"Question {question.id}: {question.stem.plain_text()}")
    if "choices" in roles:
        for choice in question.choices:
            lines.append(f"[{choice.id}] {choice.content.plain_text()}")
    if "answer" in roles and question.answer:
        lines.append(f"Answer: {question.answer.kind}:{question.answer.value}")
    if "analysis" in roles and question.metadata.get("analysis"):
        lines.append(f"Analysis: {question.metadata['analysis']}")
    if "solution" in roles and question.solution:
        lines.append(f"Solution: {question.solution.plain_text()}")
    return lines


def render_block(question: Question, block: Mapping[str, Any], mode: str) -> str:
    lines = _content_lines(question, list(block["roles"]))
    prefix = f"[DQWB {block['block_id']} | {question.id} | {question_fingerprint(question)}]"
    if mode == "compose":
        prefix = "[compose] " + prefix
    return prefix + "\n" + "\n".join(lines)


@dataclass(frozen=True, slots=True)
class BlockResult:
    block_id: str
    status: str
    content: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        values = {
            "block_id": self.block_id,
            "status": self.status,
            "content": self.content,
            "reason": self.reason,
        }
        return {key: value for key, value in values.items() if value is not None}


class WordPublisher:
    """Refresh managed blocks against a reviewed canonical question set."""

    def __init__(self, question_set: QuestionSet):
        self.question_set = question_set

    def insert(
        self,
        question_id: str,
        *,
        block_id: str,
        mode: str = "compose",
        roles: list[str] | None = None,
    ) -> dict[str, Any]:
        """Resolve a new block against the current canonical revision."""

        question = next(
            (item for item in self.question_set.questions if item.id == question_id), None
        )
        if question is None:
            raise StaleBlockError(f"Question not found: {question_id}")
        if not block_id or any(character in block_id for character in "|\r\n"):
            raise WordPublishingError("block_id must be a non-empty tag-safe value.")
        if mode not in {"compose", "final"}:
            raise WordPublishingError("mode must be compose or final.")
        block = {
            "block_id": block_id,
            "question_id": question.id,
            "question_fingerprint": question_fingerprint(question),
            "roles": roles or ["stem", "choices", "answer", "solution"],
            "display": {},
        }
        return {
            "status": "inserted",
            "block": block,
            "content": render_block(question, block, mode),
        }

    def refresh(
        self,
        envelope: Mapping[str, Any],
        current: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> list[BlockResult]:
        env = validate_envelope(envelope)
        by_id = {question.id: question for question in self.question_set.questions}
        current = current or {}
        results: list[BlockResult] = []
        for block in env["blocks"]:
            block_id = block["block_id"]
            question = by_id.get(block["question_id"])
            previous = current.get(block_id, {})
            if question is None:
                results.append(
                    BlockResult(block_id, "stale", previous.get("content"), "missing-question")
                )
                continue
            actual = question_fingerprint(question)
            if actual != block["question_fingerprint"]:
                results.append(
                    BlockResult(block_id, "stale", previous.get("content"), "revision-mismatch")
                )
                continue
            try:
                content = render_block(question, block, env["mode"])
                results.append(BlockResult(block_id, "refreshed", content))
            except Exception as exc:  # pragma: no cover - defensive renderer boundary
                results.append(BlockResult(block_id, "failed", previous.get("content"), str(exc)))
        return results


def export_word_publishing(
    question_set: QuestionSet,
    target: Path,
    envelope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a DOCX containing managed ``w:sdt`` reference blocks."""

    try:
        import docx
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Word publishing requires: pip install 'dq-questionbank-core[docx]'") from exc
    env = validate_envelope(envelope or build_envelope(question_set))
    by_id = {question.id: question for question in question_set.questions}
    document = docx.Document()
    document.core_properties.title = question_set.title
    document.core_properties.subject = "DQ QuestionBank managed Word publishing document"
    document.add_heading(question_set.title, level=0)
    for block in env["blocks"]:
        question = by_id[block["question_id"]]
        sdt = OxmlElement("w:sdt")
        properties = OxmlElement("w:sdtPr")
        alias = OxmlElement("w:alias")
        alias.set(qn("w:val"), f"DQWB {block['block_id']}")
        tag = OxmlElement("w:tag")
        tag_value = (
            f"{MANAGED_TAG_PREFIX}{block['block_id']}|"
            f"{question.id}|{block['question_fingerprint']}"
        )
        tag.set(qn("w:val"), tag_value)
        sid = OxmlElement("w:id")
        stable_id = int(hashlib.sha256(block["block_id"].encode()).hexdigest()[:7], 16)
        sid.set(qn("w:val"), str(stable_id))
        properties.extend([alias, tag, sid])
        content = OxmlElement("w:sdtContent")
        paragraph = OxmlElement("w:p")
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = render_block(question, block, env["mode"])
        run.append(text)
        paragraph.append(run)
        content.append(paragraph)
        sdt.extend([properties, content])
        document.element.body.append(sdt)
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(target)
    return env


def extract_managed_blocks(source: Path) -> dict[str, dict[str, str]]:
    """Read managed block metadata without executing anything in the DOCX."""

    import xml.etree.ElementTree as ET

    namespace = {"w": _W_NS}
    with ZipFile(source) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    blocks: dict[str, dict[str, str]] = {}
    for sdt in root.findall(".//w:sdt", namespace):
        tag = sdt.find("./w:sdtPr/w:tag", namespace)
        if tag is None or not str(tag.attrib.get(f"{{{_W_NS}}}val", "")).startswith(MANAGED_TAG_PREFIX):
            continue
        raw = tag.attrib[f"{{{_W_NS}}}val"][len(MANAGED_TAG_PREFIX):]
        parts = raw.split("|", 2)
        if len(parts) != 3:
            continue
        text = "".join(node.text or "" for node in sdt.findall(".//w:t", namespace))
        blocks[parts[0]] = {"question_id": parts[1], "question_fingerprint": parts[2], "content": text}
    return blocks


class _BridgeHandler(BaseHTTPRequestHandler):
    server: "WordPublishingBridge"

    def log_message(self, *_args: Any) -> None:
        return

    def _send(self, status: int, payload: Mapping[str, Any]) -> None:
        body = canonical_json(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/status":
            self._send(200, {"status": "ok", "protocol": ENVELOPE_VERSION, "credentials": "never"})
        else:
            self._send(404, {"error": "not-found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/v1/insert", "/v1/refresh"}:
            self._send(404, {"error": "not-found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BRIDGE_REQUEST_BYTES:
                raise WordPublishingError("Request body size is invalid.")
            if self.headers.get("X-DQ-Word-Protocol") != ENVELOPE_VERSION:
                raise WordPublishingError("Missing or unsupported Word protocol header.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/v1/insert":
                result = self.server.publisher.insert(
                    str(payload["question_id"]),
                    block_id=str(payload["block_id"]),
                    mode=str(payload.get("mode", "compose")),
                    roles=payload.get("roles"),
                )
                self._send(200, result)
            else:
                envelope = payload["envelope"]
                results = self.server.publisher.refresh(envelope, payload.get("current", {}))
                self._send(200, {"results": [result.to_dict() for result in results]})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, WordPublishingError) as exc:
            self._send(400, {"error": str(exc)})


class WordPublishingBridge:
    """Threaded loopback bridge for the VBA client and local tools."""

    def __init__(self, question_set: QuestionSet, host: str = "127.0.0.1", port: int = 8766):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise WordPublishingError("The bridge may bind only to a loopback host.")
        self.publisher = WordPublisher(question_set)
        server_type = _IPv6ThreadingHTTPServer if host == "::1" else ThreadingHTTPServer
        self.server = server_type((host, port), _BridgeHandler)
        self.server.publisher = self.publisher  # type: ignore[attr-defined]
        self.thread: threading.Thread | None = None

    @property
    def origin(self) -> str:
        host, port = self.server.server_address[:2]
        authority = f"[{host}]" if ":" in host else host
        return f"http://{authority}:{port}"

    def start(self) -> None:
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        if self.thread:
            self.thread.join(timeout=2)


class _IPv6ThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6
