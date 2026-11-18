"""pricing as a provider: replay every consumer pact against the real handler over HTTP."""

import pytest
from pact import Verifier

from lambda_http import serve
from pricing.handler import handler
from testkit.contracts import verify, with_pacts

pytestmark = pytest.mark.contract

CONSUMERS = ["quotes"]


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_pricing_honours_consumer_pact(consumer: str) -> None:
    with serve(handler) as base_url:
        verify(
            with_pacts(
                Verifier("pricing", host="127.0.0.1").add_transport(url=base_url),
                consumer,
                "pricing",
            )
        )
