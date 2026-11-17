"""Lambda entry point: POST /prices/quote."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from lambda_http import HttpError, Request, Response, Router, json_response
from pricing.engine import PricingError, quote_price

log = logging.getLogger(__name__)
router = Router()


@router.route("POST", "/prices/quote")
def price_quote(request: Request) -> Response:
    data = request.json()
    missing = [k for k in ("annual_kwh", "tariff_code", "region") if k not in data]
    if missing:
        raise HttpError(400, f"missing fields: {', '.join(missing)}")
    try:
        annual_kwh = Decimal(str(data["annual_kwh"]))
    except InvalidOperation as exc:
        raise HttpError(400, "annual_kwh must be a number") from exc

    try:
        price = quote_price(annual_kwh, str(data["tariff_code"]), str(data["region"]))
    except PricingError as exc:
        raise HttpError(422, str(exc)) from exc

    log.info("priced %s kWh on %s", annual_kwh, price.tariff_code)
    return json_response(200, price.to_dict())


handler = router
