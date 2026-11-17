"""quotes → pricing, consumer side.

Pins exactly what PricingClient relies on. If pricing renames or drops one of these
fields, provider verification in the pricing pipeline fails before merge.
"""

from collections.abc import Iterator

import pytest
from pact import Pact, match

from quotes.pricing_client import PricingClient, PricingRejected
from testkit.contracts import PACT_DIR

pytestmark = pytest.mark.contract


@pytest.fixture
def pact() -> Iterator[Pact]:
    pact = Pact("quotes", "pricing").with_specification("V4")
    yield pact
    pact.write_file(PACT_DIR)  # merges interactions into pacts/quotes-pricing.json


def test_price_for_known_tariff(pact: Pact) -> None:
    request = {"annual_kwh": 20000, "tariff_code": "FIXED-12M", "region": "NW"}
    (
        pact.upon_receiving("a price request for a known tariff")
        .with_request("POST", "/prices/quote")
        .with_header("content-type", "application/json")
        .with_body(request, content_type="application/json")
        .will_respond_with(200)
        .with_body(
            {
                "unit_rate": match.number(24.5),
                "standing_charge": match.number(55.0),
                "annual_cost": match.number(5100.75),
                "currency": match.str("GBP"),
            },
            content_type="application/json",
        )
    )

    with pact.serve() as server:
        price = PricingClient(str(server.url)).quote(20000, "FIXED-12M", "NW")

    assert price.currency == "GBP"
    assert price.annual_cost > 0


def test_unknown_tariff_is_rejected(pact: Pact) -> None:
    request = {"annual_kwh": 20000, "tariff_code": "NOT-A-TARIFF", "region": "NW"}
    (
        pact.upon_receiving("a price request for an unknown tariff")
        .with_request("POST", "/prices/quote")
        .with_header("content-type", "application/json")
        .with_body(request, content_type="application/json")
        .will_respond_with(422)
        .with_body(
            {"error": match.str("unknown tariff_code: NOT-A-TARIFF")},
            content_type="application/json",
        )
    )

    with pact.serve() as server, pytest.raises(PricingRejected):
        PricingClient(str(server.url)).quote(20000, "NOT-A-TARIFF", "NW")
