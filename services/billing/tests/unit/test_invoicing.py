from decimal import Decimal

import pytest

from billing.invoicing import NotBillable, build_invoice_line
from billing.quotes_client import QuoteView


def quote(status="ACCEPTED", annual_cost="5100.75"):
    return QuoteView("Q-1", "C-42", status, Decimal(annual_cost), "GBP")


def test_spreads_annual_cost_over_twelve_months():
    line = build_invoice_line(quote(annual_cost="5100.75"))

    assert line.monthly_amount == Decimal("425.06")  # 425.0625 rounded half-up
    assert line.currency == "GBP"
    assert line.customer_id == "C-42"
    assert "Q-1" in line.description


def test_monthly_amount_rounds_half_up_to_the_penny():
    assert build_invoice_line(quote(annual_cost="0.30")).monthly_amount == Decimal("0.03")


@pytest.mark.parametrize("status", ["PENDING", "EXPIRED"])
def test_only_accepted_quotes_are_billable(status):
    with pytest.raises(NotBillable, match=status):
        build_invoice_line(quote(status=status))
