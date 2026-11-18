"""Business electricity pricing.

Rates are in pence: unit rate per kWh, standing charge per day.
Annual cost is in pounds, rounded to the penny.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PENNY = Decimal("0.01")
DAYS_PER_YEAR = 365
MAX_ANNUAL_KWH = Decimal(50_000_000)


@dataclass(frozen=True)
class Tariff:
    unit_rate: Decimal  # p/kWh, before regional uplift and volume discount
    standing_charge: Decimal  # p/day


TARIFFS: dict[str, Tariff] = {
    "FIXED-12M": Tariff(Decimal("24.50"), Decimal("55.00")),
    "FIXED-24M": Tariff(Decimal("23.80"), Decimal("55.00")),
    "FLEX": Tariff(Decimal("22.10"), Decimal("48.00")),
}

# Network costs differ by region; applied to the unit rate only.
REGION_UPLIFT: dict[str, Decimal] = {
    "LDN": Decimal("1.04"),
    "NW": Decimal("1.00"),
    "SCO": Decimal("0.98"),
}

# (threshold kWh/year, discount on unit rate). Highest matching tier wins.
VOLUME_TIERS: list[tuple[Decimal, Decimal]] = [
    (Decimal(250_000), Decimal("0.06")),
    (Decimal(100_000), Decimal("0.03")),
]


class PricingError(ValueError):
    """Input can't be priced (unknown tariff/region, out-of-range consumption)."""


@dataclass(frozen=True)
class PriceBreakdown:
    tariff_code: str
    unit_rate: Decimal
    standing_charge: Decimal
    annual_cost: Decimal
    currency: str = "GBP"

    def to_dict(self) -> dict[str, object]:
        return {
            "tariff_code": self.tariff_code,
            "unit_rate_pence": float(self.unit_rate),
            "standing_charge": float(self.standing_charge),
            "annual_cost": float(self.annual_cost),
            "currency": self.currency,
        }


def volume_discount(annual_kwh: Decimal) -> Decimal:
    for threshold, discount in VOLUME_TIERS:
        if annual_kwh >= threshold:
            return discount
    return Decimal(0)


def quote_price(annual_kwh: Decimal, tariff_code: str, region: str) -> PriceBreakdown:
    if annual_kwh <= 0 or annual_kwh > MAX_ANNUAL_KWH:
        raise PricingError(f"annual_kwh must be in (0, {MAX_ANNUAL_KWH}]")
    tariff = TARIFFS.get(tariff_code)
    if tariff is None:
        raise PricingError(f"unknown tariff_code: {tariff_code}")
    uplift = REGION_UPLIFT.get(region)
    if uplift is None:
        raise PricingError(f"unknown region: {region}")

    unit_rate = (tariff.unit_rate * uplift * (1 - volume_discount(annual_kwh))).quantize(
        PENNY, ROUND_HALF_UP
    )
    annual_pence = annual_kwh * unit_rate + tariff.standing_charge * DAYS_PER_YEAR
    annual_cost = (annual_pence / 100).quantize(PENNY, ROUND_HALF_UP)
    return PriceBreakdown(tariff_code, unit_rate, tariff.standing_charge, annual_cost)
