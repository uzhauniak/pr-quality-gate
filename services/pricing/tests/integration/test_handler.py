"""Handler-level tests: event in, response out, response checked against openapi.yaml."""

import json
from pathlib import Path

import pytest

from lambda_http.router import make_event
from pricing.handler import handler
from testkit.openapi import assert_matches_spec

SPEC = Path(__file__).parents[2] / "openapi.yaml"
PATH = "/prices/quote"


def call(body):
    response = handler(make_event("POST", PATH, body))
    assert_matches_spec(SPEC, PATH, "POST", response)
    return response


def test_prices_a_valid_request():
    response = call({"annual_kwh": 20_000, "tariff_code": "FIXED-12M", "region": "NW"})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["unit_rate"] == 24.5
    assert body["annual_cost"] == 5100.75


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"tariff_code": "FLEX", "region": "NW"}, 400),
        ({"annual_kwh": "lots", "tariff_code": "FLEX", "region": "NW"}, 400),
        ({"annual_kwh": 1000, "tariff_code": "NOPE", "region": "NW"}, 422),
        ("not json", 400),
    ],
)
def test_rejects_bad_requests_with_documented_errors(body, status):
    assert call(body)["statusCode"] == status


def test_unknown_route_is_404():
    assert handler(make_event("GET", "/nope"))["statusCode"] == 404
