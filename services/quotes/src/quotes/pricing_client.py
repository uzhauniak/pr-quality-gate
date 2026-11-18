"""HTTP client for the pricing service. The Pact consumer test pins what we rely on."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal


class PricingUnavailable(RuntimeError):
    """Pricing could not be reached or returned an unexpected response."""


class PricingRejected(ValueError):
    """Pricing understood the request but refused to price it."""


@dataclass(frozen=True)
class PriceQuote:
    unit_rate: Decimal
    standing_charge: Decimal
    annual_cost: Decimal
    currency: str

    def to_dict(self) -> dict[str, object]:
        return {
            "unit_rate": float(self.unit_rate),
            "standing_charge": float(self.standing_charge),
            "annual_cost": float(self.annual_cost),
            "currency": self.currency,
        }


class PricingClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    def quote(self, annual_kwh: float, tariff_code: str, region: str) -> PriceQuote:
        payload = json.dumps(
            {"annual_kwh": annual_kwh, "tariff_code": tariff_code, "region": region}
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/prices/quote",
            data=payload,
            method="POST",
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as err:
            if err.code == 422:
                raise PricingRejected(json.loads(err.read()).get("error", "rejected")) from err
            raise PricingUnavailable(f"pricing returned HTTP {err.code}") from err
        except (urllib.error.URLError, TimeoutError) as err:
            raise PricingUnavailable(str(err)) from err

        try:
            return PriceQuote(
                unit_rate=Decimal(str(body["unit_rate"])),
                standing_charge=Decimal(str(body["standing_charge"])),
                annual_cost=Decimal(str(body["annual_cost"])),
                currency=body["currency"],
            )
        except (KeyError, TypeError) as err:
            raise PricingUnavailable(f"unexpected pricing response: missing {err}") from err
