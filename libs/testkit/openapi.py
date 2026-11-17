"""Validate handler responses against a service's own openapi.yaml.

This is the provider's self-check ("do I return what I document?"). It complements
Pact, which checks "do I return what my consumers actually use?".
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from openapi_schema_validator import OAS31Validator, validate


@cache
def _load(spec_path: Path) -> dict[str, Any]:
    return yaml.safe_load(spec_path.read_text(encoding="utf-8"))


def _resolve(node: Any, spec: dict[str, Any]) -> Any:
    """Inline local `#/components/...` refs so the schema validates standalone."""
    if isinstance(node, dict):
        if "$ref" in node:
            target: Any = spec
            for part in node["$ref"].removeprefix("#/").split("/"):
                target = target[part]
            return _resolve(target, spec)
        return {key: _resolve(value, spec) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve(item, spec) for item in node]
    return node


def assert_matches_spec(
    spec_path: Path, path_template: str, method: str, response: dict[str, Any]
) -> None:
    spec = _load(spec_path)
    operation = spec["paths"][path_template][method.lower()]
    status = str(response["statusCode"])
    assert status in operation["responses"], (
        f"{method.upper()} {path_template} returned undocumented status {status}"
    )
    documented = _resolve(operation["responses"][status], spec)
    content = documented.get("content", {}).get("application/json")
    if content is None:
        return
    schema = _resolve(content["schema"], spec)
    validate(json.loads(response["body"]), schema, cls=OAS31Validator)
