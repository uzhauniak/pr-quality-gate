"""Handler-level tests with a fake quotes dependency; responses checked against openapi.yaml."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from billing.handler import build_router
from billing.quotes_client import QuoteMissing, QuotesUnavailable, QuoteView
from lambda_http.router import make_event
from testkit.openapi import assert_matches_spec

SPEC = Path(__file__).parents[2] / "openapi.yaml"
PATH = "/invoice-lines"


class FakeQuotes:
    def __init__(self, result):
        self.result = result

    def get_quote(self, quote_id):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def call(quotes, body):
    response = build_router(quotes)(make_event("POST", PATH, body))
    assert_matches_spec(SPEC, PATH, "POST", response)
    return response


def test_creates_invoice_line_for_accepted_quote():
    quotes = FakeQuotes(QuoteView("Q-1", "C-42", "ACCEPTED", Decimal("1200.00"), "GBP"))

    response = call(quotes, {"quote_id": "Q-1"})

    assert response["statusCode"] == 201
    assert json.loads(response["body"])["monthly_amount"] == 100.0


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (QuoteView("Q-1", "C-42", "PENDING", Decimal("1200.00"), "GBP"), 409),
        (QuoteMissing("Q-1"), 404),
        (QuotesUnavailable("timeout"), 502),
    ],
)
def test_maps_failures_to_documented_statuses(result, status):
    assert call(FakeQuotes(result), {"quote_id": "Q-1"})["statusCode"] == status


def test_quote_id_is_required():
    assert call(FakeQuotes(None), {})["statusCode"] == 400
