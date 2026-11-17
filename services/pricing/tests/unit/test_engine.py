from decimal import Decimal

import pytest

from pricing.engine import PricingError, quote_price, volume_discount


def test_small_business_in_baseline_region_pays_list_price():
    price = quote_price(Decimal(20_000), "FIXED-12M", "NW")

    assert price.unit_rate == Decimal("24.50")
    assert price.standing_charge == Decimal("55.00")
    # 20,000 kWh * 24.50p + 365 days * 55p = 490,000p + 20,075p
    assert price.annual_cost == Decimal("5100.75")
    assert price.currency == "GBP"


def test_regional_uplift_applies_to_unit_rate_only():
    nw = quote_price(Decimal(20_000), "FLEX", "NW")
    ldn = quote_price(Decimal(20_000), "FLEX", "LDN")

    assert ldn.unit_rate == Decimal("22.98")  # 22.10 * 1.04, rounded half-up
    assert ldn.standing_charge == nw.standing_charge


@pytest.mark.parametrize(
    ("annual_kwh", "expected"),
    [
        (Decimal(50_000), Decimal(0)),
        (Decimal(150_000), Decimal("0.03")),
        (Decimal(400_000), Decimal("0.06")),
    ],
)
def test_volume_discount_tiers(annual_kwh, expected):
    assert volume_discount(annual_kwh) == expected


def test_large_consumer_gets_discounted_unit_rate():
    price = quote_price(Decimal(400_000), "FIXED-24M", "NW")

    assert price.unit_rate == Decimal("22.37")  # 23.80 * 0.94


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"annual_kwh": Decimal(0), "tariff_code": "FLEX", "region": "NW"}, "annual_kwh"),
        ({"annual_kwh": Decimal(-5), "tariff_code": "FLEX", "region": "NW"}, "annual_kwh"),
        ({"annual_kwh": Decimal(10**9), "tariff_code": "FLEX", "region": "NW"}, "annual_kwh"),
        ({"annual_kwh": Decimal(1000), "tariff_code": "NOPE", "region": "NW"}, "tariff"),
        ({"annual_kwh": Decimal(1000), "tariff_code": "FLEX", "region": "MARS"}, "region"),
    ],
)
def test_rejects_unpriceable_input(kwargs, message):
    with pytest.raises(PricingError, match=message):
        quote_price(**kwargs)
