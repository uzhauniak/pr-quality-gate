"""Tiny toolkit for Lambda-style HTTP handlers (API Gateway HTTP API, payload v2.0).

- `Router` maps (method, path template) to functions and turns events into responses.
- `serve()` exposes any handler on localhost, so contract verification can hit
  the real handler code over HTTP without AWS.
"""

from lambda_http.local_server import serve
from lambda_http.router import HttpError, Request, Response, Router, json_response

__all__ = ["HttpError", "Request", "Response", "Router", "json_response", "serve"]
