"""Loopback-only HTTP server for the visual local workspace."""

from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .case_database import CaseDatabase, CaseDatabaseError, bundled_case_database
from .storage import WorkspaceStorage
from .validation import ValidationError

_MAX_BODY_BYTES = 5 * 1024 * 1024
_SET_ROUTE = re.compile(r"^/api/sets/([^/]+)$")
_STATIC_FILES = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}


def create_server(
    workspace: Path,
    host: str = "127.0.0.1",
    port: int = 8766,
    case_database: Path | None = None,
) -> ThreadingHTTPServer:
    """Create a server bound only to a loopback address."""
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("DQ QuestionBank Local only permits loopback hosts.")
    storage = WorkspaceStorage(workspace)
    case = CaseDatabase(case_database or bundled_case_database())

    class WorkspaceHandler(_Handler):
        workspace_storage = storage
        public_case = case

    return ThreadingHTTPServer((host, port), WorkspaceHandler)


class _Handler(BaseHTTPRequestHandler):
    workspace_storage: WorkspaceStorage
    public_case: CaseDatabase
    server_version = "DQQuestionBankLocal/0.1"
    sys_version = ""

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/sets":
            self._send_json(HTTPStatus.OK, {"sets": self.workspace_storage.list_sets()})
            return
        if path == "/api/workspace":
            self._send_json(HTTPStatus.OK, {"mode": "local-only"})
            return
        if path == "/api/case":
            try:
                self._send_json(HTTPStatus.OK, self.public_case.info())
            except CaseDatabaseError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        match = _SET_ROUTE.fullmatch(path)
        if match:
            self._serve_set(unquote(match.group(1)))
            return
        if path in _STATIC_FILES:
            self._serve_static(_STATIC_FILES[path])
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Not found.")

    def do_POST(self) -> None:  # noqa: N802
        if not self._mutation_is_same_origin():
            self._send_error(HTTPStatus.FORBIDDEN, "Cross-origin writes are not allowed.")
            return
        path = urlparse(self.path).path
        if path == "/api/case/load":
            self._load_public_case()
            return
        if path != "/api/import":
            self._send_error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        self._save_request(expected_id=None, status=HTTPStatus.CREATED)

    def do_PUT(self) -> None:  # noqa: N802
        if not self._mutation_is_same_origin():
            self._send_error(HTTPStatus.FORBIDDEN, "Cross-origin writes are not allowed.")
            return
        match = _SET_ROUTE.fullmatch(urlparse(self.path).path)
        if not match:
            self._send_error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        self._save_request(expected_id=unquote(match.group(1)), status=HTTPStatus.OK)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, PUT, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _load_public_case(self) -> None:
        try:
            info = self.public_case.info()
            if self.workspace_storage.contains(info["id"]):
                payload = self.workspace_storage.load(info["id"])
            else:
                payload = self.public_case.load()
                self.workspace_storage.save(payload)
        except (CaseDatabaseError, ValidationError, ValueError, OSError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(HTTPStatus.OK, payload)

    def _serve_set(self, question_set_id: str) -> None:
        try:
            payload = self.workspace_storage.load(question_set_id)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Question set not found.")
            return
        except (ValueError, OSError, json.JSONDecodeError):
            self._send_error(HTTPStatus.BAD_REQUEST, "Question set cannot be read safely.")
            return
        self._send_json(HTTPStatus.OK, payload)

    def _save_request(self, expected_id: str | None, status: HTTPStatus) -> None:
        try:
            payload = self._read_request_json()
            if expected_id is not None and payload.get("id") != expected_id:
                raise ValidationError("The request id does not match the URL.")
            self.workspace_storage.save(payload)
        except (ValidationError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except OSError:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to save question set.")
            return
        self._send_json(status, payload)

    def _read_request_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValidationError("Content-Type must be application/json.")
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise ValidationError("Content-Length is required.")
        try:
            size = int(content_length)
        except ValueError as exc:
            raise ValidationError("Content-Length is invalid.") from exc
        if size < 1 or size > _MAX_BODY_BYTES:
            raise ValidationError("Request body must be between 1 byte and 5 MiB.")
        try:
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Request body must be valid UTF-8 JSON.") from exc
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object.")
        return payload

    def _serve_static(self, filename: str) -> None:
        resource = files("dq_questionbank_local").joinpath("web", filename)
        try:
            content = resource.read_bytes()
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def _mutation_is_same_origin(self) -> bool:
        host = self.headers.get("Host", "")
        host_name = urlparse(f"//{host}").hostname
        if host_name not in {"127.0.0.1", "::1", "localhost"}:
            return False
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site and fetch_site not in {"same-origin", "none"}:
            return False
        origin = self.headers.get("Origin")
        if origin:
            parsed_origin = urlparse(origin)
            if parsed_origin.scheme != "http" or parsed_origin.netloc != host:
                return False
        return True

    def end_headers(self) -> None:
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """Keep request logs free of request bodies and question content."""
        return
