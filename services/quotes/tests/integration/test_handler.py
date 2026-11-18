"""Handler-level tests with a fake pricing dependency; responses checked against openapi.yaml."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from lambda_http.router import make_event
from quotes.handler import build_router
from quotes.pricing_client import PriceQuote, PricingRejected, PricingUnavailable
from quotes.service import InMemoryQuoteStore, QuoteService
from testkit.openapi import assert_matches_spec

SPEC = Path(__file__).parents[2] / "openapi.yaml"
REQUEST = {"customer_id": "C-1", "annual_kwh": 20_000, "tariff_code": "FIXED-12M", "region": "NW"}


class StubPricing:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def quote(self, annual_kwh, tariff_code, region):
        if self.error:
            raise self.error
        return PriceQuote(Decimal("24.50"), Decimal("55.00"), Decimal("5100.75"), "GBP")


def make_handler(pricing=None):
    return build_router(QuoteService(pricing or StubPricing(), InMemoryQuoteStore()))


def call(handler, method, path, template, body=None):
    response = handler(make_event(method, path, body))
    assert_matches_spec(SPEC, template, method, response)
    return response, json.loads(response["body"])


def test_create_get_accept_flow():
    handler = make_handler()

    response, created = call(handler, "POST", "/quotes", "/quotes", REQUEST)
    assert response["statusCode"] == 201
    assert created["status"] == "PENDING"
    assert created["price"]["annual_cost"] == 5100.75

    path = f"/quotes/{created['id']}"
    _, fetched = call(handler, "GET", path, "/quotes/{quote_id}")
    assert fetched == created

    response, accepted = call(handler, "POST", f"{path}/accept", "/quotes/{quote_id}/accept")
    assert response["statusCode"] == 200
    assert accepted["status"] == "ACCEPTED"

    response, _ = call(handler, "POST", f"{path}/accept", "/quotes/{quote_id}/accept")
    assert response["statusCode"] == 409


@pytest.mark.parametrize(
    ("error", "status"),
    [(PricingRejected("unknown tariff_code: X"), 422), (PricingUnavailable("timeout"), 502)],
)
def test_pricing_failures_map_to_documented_statuses(error, status):
    response, _ = call(make_handler(StubPricing(error)), "POST", "/quotes", "/quotes", REQUEST)
    assert response["statusCode"] == status


def test_missing_fields_is_400():
    response, body = call(make_handler(), "POST", "/quotes", "/quotes", {"customer_id": "C-1"})
    assert response["statusCode"] == 400
    assert "annual_kwh" in body["error"]


def test_unknown_quote_is_404():
    response, _ = call(make_handler(), "GET", "/quotes/Q-NOPE", "/quotes/{quote_id}")
    assert response["statusCode"] == 404


def test_deployed_handler_reaches_pricing_through_the_same_api(monkeypatch):
    from quotes import handler as module

    monkeypatch.delenv("PRICING_URL", raising=False)
    monkeypatch.setattr(module._pricing, "base_url", "http://localhost:8001")
    event = make_event("GET", "/quotes/Q-NOPE")
    event["requestContext"]["domainName"] = "abc123.execute-api.eu-north-1.amazonaws.com"

    assert module.handler(event)["statusCode"] == 404
    assert module._pricing.base_url == "https://abc123.execute-api.eu-north-1.amazonaws.com"
