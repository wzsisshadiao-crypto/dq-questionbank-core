"""Small local-only static server for the browser playground."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import as_file, files


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("The playground is local-only; use 127.0.0.1, localhost, or ::1.")
    resource = files("dq_questionbank").joinpath("web")
    with as_file(resource) as web_root:
        handler = partial(SimpleHTTPRequestHandler, directory=str(web_root))
        server = ThreadingHTTPServer((host, port), handler)
        print(f"DQ QuestionBank Playground is available at http://{host}:{port}")
        print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
