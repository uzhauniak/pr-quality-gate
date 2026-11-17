from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from lambda_http.router import make_event

LambdaHandler = Callable[[dict[str, Any], Any], dict[str, Any]]


@contextmanager
def serve(handler: LambdaHandler) -> Iterator[str]:
    """Run a Lambda-style handler behind a localhost HTTP server; yields its base URL."""

    class _Adapter(BaseHTTPRequestHandler):
        def _dispatch(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(length).decode() if length else None
            event = make_event(self.command, urlsplit(self.path).path, body)
            result = handler(event, None)
            payload = (result.get("body") or "").encode()
            self.send_response(result["statusCode"])
            for name, value in (result.get("headers") or {}).items():
                self.send_header(name, value)
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _dispatch

        def log_message(self, format: str, *args: Any) -> None:  # keep test output clean
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Adapter)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
