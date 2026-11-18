"""Smoke tests against a deployed environment, run after every deploy.

    python quality/smoke.py --base-url https://<api-id>.execute-api.<region>.amazonaws.com

Each check exercises one real network path in the cloud, and responses are validated
against the services' own OpenAPI specs:
  client → pricing;  client → quotes → pricing;  client → billing → quotes.
Only 4xx paths are used for error cases, so smoke traffic never trips the canary alarms.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs"))

from testkit.openapi import assert_matches_spec  # noqa: E402

SPECS = {s: ROOT / "services" / s / "openapi.yaml" for s in ("pricing", "quotes", "billing")}
PRICE_REQUEST = {"annual_kwh": 20000, "tariff_code": "FIXED-12M", "region": "NW"}


@dataclass
class Check:
    name: str
    service: str
    method: str
    path: str
    template: str
    body: dict[str, Any] | None
    status: int
    expect: Callable[[dict[str, Any]], None] = lambda body: None


def call(base_url: str, method: str, path: str, body: Any, retries: int = 3) -> dict[str, Any]:
    """Return an API Gateway-shaped response dict, retrying transient failures."""
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            data=data,
            method=method,
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return {"statusCode": response.status, "body": response.read().decode()}
        except urllib.error.HTTPError as err:
            if err.code < 500 or attempt == retries:
                return {"statusCode": err.code, "body": err.read().decode()}
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def checks() -> list[Check]:
    def priced(body: dict[str, Any]) -> None:
        assert body["currency"] == "GBP" and body["annual_cost"] > 0, body

    def quoted(body: dict[str, Any]) -> None:
        assert body["status"] == "PENDING", body
        assert body["price"]["annual_cost"] > 0, body  # came from pricing over the network

    return [
        Check("pricing prices a quote", "pricing", "POST", "/prices/quote", "/prices/quote",
              PRICE_REQUEST, 200, priced),
        Check("pricing rejects an unknown tariff", "pricing", "POST", "/prices/quote",
              "/prices/quote", {**PRICE_REQUEST, "tariff_code": "NOPE"}, 422),
        Check("quotes → pricing: create a priced quote", "quotes", "POST", "/quotes", "/quotes",
              {"customer_id": "SMOKE", **PRICE_REQUEST}, 201, quoted),
        Check("quotes → pricing: rejection propagates", "quotes", "POST", "/quotes", "/quotes",
              {"customer_id": "SMOKE", **PRICE_REQUEST, "tariff_code": "NOPE"}, 422),
        Check("billing → quotes: unknown quote is 404", "billing", "POST", "/invoice-lines",
              "/invoice-lines", {"quote_id": "Q-SMOKE-MISSING"}, 404),
    ]  # fmt: skip


def run(base_url: str) -> list[tuple[Check, str | None]]:
    results = []
    for check in checks():
        try:
            response = call(base_url, check.method, check.path, check.body)
            assert response["statusCode"] == check.status, (
                f"expected {check.status}, got {response['statusCode']}: {response['body'][:300]}"
            )
            assert_matches_spec(SPECS[check.service], check.template, check.method, response)
            check.expect(json.loads(response["body"]))
            error = None
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:400]
        print(f"{'ok  ' if error is None else 'FAIL'} {check.name}")
        if error:
            print(f"     {error}")
        results.append((check, error))
    return results


def summary(base_url: str, results: list[tuple[Check, str | None]]) -> str:
    lines = [f"## Smoke tests: `{base_url}`", "", "| | Check | |", "|---|---|---|"]
    for check, error in results:
        detail = f"`{error}`" if error else f"{check.method} {check.path} → {check.status}"
        lines.append(f"| {'✅' if error is None else '❌'} | {check.name} | {detail} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--summary", type=Path, help="append a markdown table here")
    args = parser.parse_args()

    results = run(args.base_url)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as out:
            out.write(summary(args.base_url, results))
    return 1 if any(error for _, error in results) else 0


if __name__ == "__main__":
    sys.exit(main())
