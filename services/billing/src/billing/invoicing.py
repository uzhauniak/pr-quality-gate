"""Turns an accepted quote into a monthly invoice line."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from billing.quotes_client import QuoteView

PENNY = Decimal("0.01")
MONTHS = 12


class NotBillable(ValueError):
    pass


@dataclass(frozen=True)
class InvoiceLine:
    quote_id: str
    customer_id: str
    description: str
    monthly_amount: Decimal
    currency: str

    def to_dict(self) -> dict[str, object]:
        return {
            "quote_id": self.quote_id,
            "customer_id": self.customer_id,
            "description": self.description,
            "monthly_amount": float(self.monthly_amount),
            "currency": self.currency,
        }


def build_invoice_line(quote: QuoteView) -> InvoiceLine:
    """Spread the annual cost evenly over twelve monthly payments."""
    if quote.status != "ACCEPTED":
        raise NotBillable(f"quote {quote.id} is {quote.status}, expected ACCEPTED")
    monthly = (quote.annual_cost / MONTHS).quantize(PENNY, ROUND_HALF_UP)
    return InvoiceLine(
        quote_id=quote.id,
        customer_id=quote.customer_id,
        description=f"Electricity supply, monthly instalment (quote {quote.id})",
        monthly_amount=monthly,
        currency=quote.currency,
    )
