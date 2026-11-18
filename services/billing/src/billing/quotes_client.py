"""HTTP client for the quotes service.

Reads only the fields billing needs. That is the point of consumer-driven
contracts: quotes may change anything else without breaking billing.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal


class QuoteMissing(LookupError):
    pass


class QuotesUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class QuoteView:
    id: str
    customer_id: str
    status: str
    annual_cost: Decimal
    currency: str


class QuotesClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_quote(self, quote_id: str) -> QuoteView:
        url = f"{self.base_url}/quotes/{quote_id}"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise QuoteMissing(quote_id) from err
            raise QuotesUnavailable(f"quotes returned HTTP {err.code}") from err
        except (urllib.error.URLError, TimeoutError) as err:
            raise QuotesUnavailable(str(err)) from err

        return QuoteView(
            id=body["id"],
            customer_id=body["customer_id"],
            status=body["status"],
            annual_cost=Decimal(str(body["price"]["annual_cost"])),
            currency=body["price"]["currency"],
        )
