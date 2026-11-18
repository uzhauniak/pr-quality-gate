"""quotes as a provider: replay every consumer pact against the real handler over HTTP."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pact import Verifier

from lambda_http import serve
from quotes.handler import build_router
from quotes.pricing_client import PriceQuote
from quotes.service import InMemoryQuoteStore, Quote, QuoteService
from testkit.contracts import verify, with_pacts

pytestmark = pytest.mark.contract

CONSUMERS = ["billing"]


class UnusedPricing:
    """Provider states seed quotes directly; no interaction should hit pricing."""

    def quote(self, *args, **kwargs):
        raise AssertionError("pricing must not be called during quotes provider verification")


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_quotes_honours_consumer_pact(consumer: str) -> None:
    store = InMemoryQuoteStore()

    def accepted_quote_exists(action: str = "setup", **_: object) -> None:
        if action == "teardown":
            store.clear()
            return
        store.put(
            Quote(
                id="Q-ACCEPTED-1",
                customer_id="C-42",
                tariff_code="FIXED-12M",
                annual_kwh=20000,
                price=PriceQuote(Decimal("24.50"), Decimal("55.00"), Decimal("5100.75"), "GBP"),
                valid_until=datetime.now(UTC) + timedelta(days=7),
                status="ACCEPTED",
            )
        )

    def no_quotes(action: str = "setup", **_: object) -> None:
        store.clear()

    handler = build_router(QuoteService(UnusedPricing(), store))
    with serve(handler) as base_url:
        verify(
            with_pacts(
                Verifier("quotes", host="127.0.0.1").add_transport(url=base_url),
                consumer,
                "quotes",
            ).state_handler(
                {
                    "quote Q-ACCEPTED-1 exists and is accepted": accepted_quote_exists,
                    "no quotes exist": no_quotes,
                },
                teardown=True,
            )
        )
