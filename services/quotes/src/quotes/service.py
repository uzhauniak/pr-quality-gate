"""Quote lifecycle: create (priced via the pricing service) → accept within validity window."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol

from quotes.pricing_client import PriceQuote

VALIDITY = timedelta(days=14)


class Pricing(Protocol):
    def quote(self, annual_kwh: float, tariff_code: str, region: str) -> PriceQuote: ...


class QuoteNotFound(LookupError):
    pass


class QuoteNotAcceptable(ValueError):
    pass


@dataclass(frozen=True)
class Quote:
    id: str
    customer_id: str
    tariff_code: str
    annual_kwh: float
    price: PriceQuote
    valid_until: datetime
    status: str = "PENDING"

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "status": self.status,
            "tariff_code": self.tariff_code,
            "annual_kwh": self.annual_kwh,
            "price": self.price.to_dict(),
            "valid_until": self.valid_until.isoformat(),
        }


class InMemoryQuoteStore:
    """Stand-in for DynamoDB; enough for the demo and for provider states."""

    def __init__(self) -> None:
        self._items: dict[str, Quote] = {}

    def get(self, quote_id: str) -> Quote | None:
        return self._items.get(quote_id)

    def put(self, quote: Quote) -> None:
        self._items[quote.id] = quote

    def clear(self) -> None:
        self._items.clear()


class QuoteService:
    def __init__(
        self,
        pricing: Pricing,
        store: InMemoryQuoteStore,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._pricing = pricing
        self._store = store
        self._clock = clock

    def create(self, customer_id: str, annual_kwh: float, tariff_code: str, region: str) -> Quote:
        price = self._pricing.quote(annual_kwh, tariff_code, region)
        quote = Quote(
            id=f"Q-{uuid.uuid4().hex[:8].upper()}",
            customer_id=customer_id,
            tariff_code=tariff_code,
            annual_kwh=annual_kwh,
            price=price,
            valid_until=self._clock() + VALIDITY,
        )
        self._store.put(quote)
        return quote

    def get(self, quote_id: str) -> Quote:
        quote = self._store.get(quote_id)
        if quote is None:
            raise QuoteNotFound(quote_id)
        return quote

    def accept(self, quote_id: str) -> Quote:
        quote = self.get(quote_id)
        if quote.status != "PENDING":
            raise QuoteNotAcceptable(f"quote is {quote.status}")
        if self._clock() > quote.valid_until:
            raise QuoteNotAcceptable("quote has expired")
        accepted = replace(quote, status="ACCEPTED")
        self._store.put(accepted)
        return accepted
