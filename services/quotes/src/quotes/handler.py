"""Lambda entry point for the quotes API."""

from __future__ import annotations

import os

from lambda_http import HttpError, Request, Response, Router, json_response
from quotes.pricing_client import PricingClient, PricingRejected, PricingUnavailable
from quotes.service import (
    InMemoryQuoteStore,
    QuoteNotAcceptable,
    QuoteNotFound,
    QuoteService,
)

REQUIRED = ("customer_id", "annual_kwh", "tariff_code", "region")


def build_router(service: QuoteService) -> Router:
    router = Router()

    @router.route("POST", "/quotes")
    def create_quote(request: Request) -> Response:
        data = request.json()
        missing = [k for k in REQUIRED if k not in data]
        if missing:
            raise HttpError(400, f"missing fields: {', '.join(missing)}")
        try:
            annual_kwh = float(data["annual_kwh"])
        except (TypeError, ValueError) as exc:
            raise HttpError(400, "annual_kwh must be a number") from exc

        try:
            quote = service.create(
                customer_id=str(data["customer_id"]),
                annual_kwh=annual_kwh,
                tariff_code=str(data["tariff_code"]),
                region=str(data["region"]),
            )
        except PricingRejected as exc:
            raise HttpError(422, str(exc)) from exc
        except PricingUnavailable as exc:
            raise HttpError(502, "pricing is unavailable") from exc
        return json_response(201, quote.to_dict())

    @router.route("GET", "/quotes/{quote_id}")
    def get_quote(request: Request) -> Response:
        try:
            return json_response(200, service.get(request.path_params["quote_id"]).to_dict())
        except QuoteNotFound as exc:
            raise HttpError(404, f"quote {exc.args[0]} not found") from exc

    @router.route("POST", "/quotes/{quote_id}/accept")
    def accept_quote(request: Request) -> Response:
        try:
            return json_response(200, service.accept(request.path_params["quote_id"]).to_dict())
        except QuoteNotFound as exc:
            raise HttpError(404, f"quote {exc.args[0]} not found") from exc
        except QuoteNotAcceptable as exc:
            raise HttpError(409, str(exc)) from exc

    return router


def _default_handler() -> Router:
    pricing = PricingClient(os.environ.get("PRICING_URL", "http://localhost:8001"))
    return build_router(QuoteService(pricing, InMemoryQuoteStore()))


handler = _default_handler()
