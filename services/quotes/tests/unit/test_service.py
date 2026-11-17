from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quotes.pricing_client import PriceQuote
from quotes.service import (
    InMemoryQuoteStore,
    QuoteNotAcceptable,
    QuoteNotFound,
    QuoteService,
)

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
PRICE = PriceQuote(Decimal("24.50"), Decimal("55.00"), Decimal("5100.75"), "GBP")


class FakePricing:
    def __init__(self) -> None:
        self.calls: list[tuple[float, str, str]] = []

    def quote(self, annual_kwh: float, tariff_code: str, region: str) -> PriceQuote:
        self.calls.append((annual_kwh, tariff_code, region))
        return PRICE


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock():
    return Clock(NOW)


@pytest.fixture
def pricing():
    return FakePricing()


@pytest.fixture
def service(pricing, clock):
    return QuoteService(pricing, InMemoryQuoteStore(), clock)


def test_create_prices_and_stores_a_pending_quote(service, pricing):
    quote = service.create("C-1", 20_000, "FIXED-12M", "NW")

    assert pricing.calls == [(20_000, "FIXED-12M", "NW")]
    assert quote.status == "PENDING"
    assert quote.price == PRICE
    assert quote.valid_until == NOW + timedelta(days=14)
    assert service.get(quote.id) == quote


def test_accept_within_validity_window(service, clock):
    quote = service.create("C-1", 20_000, "FIXED-12M", "NW")
    clock.now = NOW + timedelta(days=13)

    assert service.accept(quote.id).status == "ACCEPTED"
    assert service.get(quote.id).status == "ACCEPTED"


def test_cannot_accept_expired_quote(service, clock):
    quote = service.create("C-1", 20_000, "FIXED-12M", "NW")
    clock.now = NOW + timedelta(days=15)

    with pytest.raises(QuoteNotAcceptable, match="expired"):
        service.accept(quote.id)


def test_cannot_accept_twice(service):
    quote = service.create("C-1", 20_000, "FIXED-12M", "NW")
    service.accept(quote.id)

    with pytest.raises(QuoteNotAcceptable, match="ACCEPTED"):
        service.accept(quote.id)


def test_unknown_quote(service):
    with pytest.raises(QuoteNotFound):
        service.get("Q-NOPE")
