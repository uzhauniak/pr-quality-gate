"""billing → quotes, consumer side.

Billing declares only the fields it reads (id, customer_id, status, price.annual_cost,
price.currency). quotes can evolve everything else freely.
"""

from collections.abc import Iterator

import pytest
from pact import Pact, match

from billing.quotes_client import QuoteMissing, QuotesClient
from testkit.contracts import PACT_DIR

pytestmark = pytest.mark.contract


@pytest.fixture
def pact() -> Iterator[Pact]:
    pact = Pact("billing", "quotes").with_specification("V4")
    yield pact
    pact.write_file(PACT_DIR)


def test_fetch_accepted_quote(pact: Pact) -> None:
    (
        pact.upon_receiving("a request for an accepted quote")
        .given("quote Q-ACCEPTED-1 exists and is accepted")
        .with_request("GET", "/quotes/Q-ACCEPTED-1")
        .will_respond_with(200)
        .with_body(
            {
                "id": "Q-ACCEPTED-1",
                "customer_id": match.str("C-42"),
                "status": "ACCEPTED",
                "price": {
                    "annual_cost": match.number(5100.75),
                    "currency": match.str("GBP"),
                },
            },
            content_type="application/json",
        )
    )

    with pact.serve() as server:
        quote = QuotesClient(str(server.url)).get_quote("Q-ACCEPTED-1")

    assert quote.status == "ACCEPTED"
    assert quote.currency == "GBP"


def test_missing_quote(pact: Pact) -> None:
    (
        pact.upon_receiving("a request for a quote that does not exist")
        .given("no quotes exist")
        .with_request("GET", "/quotes/Q-MISSING")
        .will_respond_with(404)
    )

    with pact.serve() as server, pytest.raises(QuoteMissing):
        QuotesClient(str(server.url)).get_quote("Q-MISSING")
