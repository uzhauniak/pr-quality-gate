"""Lambda entry point: POST /invoice-lines."""

from __future__ import annotations

import logging
import os
from typing import Protocol

from billing.invoicing import NotBillable, build_invoice_line
from billing.quotes_client import QuoteMissing, QuotesClient, QuotesUnavailable, QuoteView
from lambda_http import HttpError, Request, Response, Router, json_response

log = logging.getLogger(__name__)


class Quotes(Protocol):
    def get_quote(self, quote_id: str) -> QuoteView: ...


def build_router(quotes: Quotes) -> Router:
    router = Router()

    @router.route("POST", "/invoice-lines")
    def create_invoice_line(request: Request) -> Response:
        quote_id = request.json().get("quote_id")
        if not isinstance(quote_id, str) or not quote_id:
            raise HttpError(400, "quote_id is required")
        try:
            line = build_invoice_line(quotes.get_quote(quote_id))
        except QuoteMissing as exc:
            raise HttpError(404, f"quote {quote_id} not found") from exc
        except NotBillable as exc:
            raise HttpError(409, str(exc)) from exc
        except QuotesUnavailable as exc:
            raise HttpError(502, "quotes is unavailable") from exc
        log.info("invoice line created for %s", quote_id)
        return json_response(201, line.to_dict())

    return router


handler = build_router(QuotesClient(os.environ.get("QUOTES_URL", "http://localhost:8002")))
