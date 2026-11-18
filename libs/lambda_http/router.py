from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Response = dict[str, Any]
Endpoint = Callable[["Request"], Response]


class HttpError(Exception):
    """Raise from an endpoint to return a JSON error response."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    path_params: dict[str, str] = field(default_factory=dict)
    body: str | None = None

    def json(self) -> dict[str, Any]:
        if not self.body:
            raise HttpError(400, "request body is required")
        try:
            data = json.loads(self.body)
        except json.JSONDecodeError as exc:
            raise HttpError(400, f"invalid JSON: {exc.msg}") from exc
        if not isinstance(data, dict):
            raise HttpError(400, "request body must be a JSON object")
        return data


def json_response(status: int, payload: Any) -> Response:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _compile(template: str) -> re.Pattern[str]:
    pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template)
    return re.compile(f"^{pattern}$")


class Router:
    """Minimal router; instances are valid Lambda handlers: `router(event, context)`."""

    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern[str], Endpoint]] = []

    def route(self, method: str, template: str) -> Callable[[Endpoint], Endpoint]:
        def register(fn: Endpoint) -> Endpoint:
            self._routes.append((method.upper(), _compile(template), fn))
            return fn

        return register

    def __call__(self, event: dict[str, Any], context: object | None = None) -> Response:
        method = event["requestContext"]["http"]["method"].upper()
        path = event["rawPath"]
        allowed_elsewhere = False
        for route_method, pattern, fn in self._routes:
            match = pattern.match(path)
            if not match:
                continue
            if route_method != method:
                allowed_elsewhere = True
                continue
            request = Request(method, path, match.groupdict(), event.get("body"))
            try:
                return fn(request)
            except HttpError as err:
                return json_response(err.status, {"error": err.message})
        if allowed_elsewhere:
            return json_response(405, {"error": f"method {method} not allowed"})
        return json_response(404, {"error": f"no route for {path}"})


def base_url_from_event(event: dict[str, Any]) -> str | None:
    """https://<api-domain> of the API Gateway that delivered this event, if any."""
    domain = (event.get("requestContext") or {}).get("domainName")
    return f"https://{domain}" if domain else None


def make_event(method: str, path: str, body: Any = None) -> dict[str, Any]:
    """Build an API Gateway v2 event. Used by tests and the local server."""
    if body is not None and not isinstance(body, str):
        body = json.dumps(body)
    return {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {"http": {"method": method.upper()}},
        "body": body,
        "isBase64Encoded": False,
    }
