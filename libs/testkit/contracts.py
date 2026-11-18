"""Shared Pact conventions.

Locally, pacts are files in pacts/ (`<consumer>-<provider>.json`). In CI,
quality/run_contracts.py --broker publishes them to a Pact Broker and sets PACT_MODE=broker,
so providers fetch pacts by consumer-version selectors and publish verification results.
"""

import os
from pathlib import Path

import pytest
from pact import Verifier

PACT_DIR = Path(__file__).resolve().parents[2] / "pacts"


def pact_file(consumer: str, provider: str) -> Path:
    path = PACT_DIR / f"{consumer}-{provider}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} not found. Consumer tests generate it; run "
            f"`python quality/run_contracts.py` instead of calling provider tests directly."
        )
    return path


def with_pacts(verifier: Verifier, consumer: str, provider: str) -> Verifier:
    if os.environ.get("PACT_MODE") != "broker":
        return verifier.add_source(pact_file(consumer, provider))

    branch = os.environ["PACT_BRANCH"]
    verifier = (
        verifier.broker_source(selector=True)  # URL + token from PACT_BROKER_* env vars
        .consumer_version(consumer=consumer, matching_branch=True)  # same feature branch
        .consumer_version(consumer=consumer, main_branch=True)
        .consumer_version(consumer=consumer, deployed_or_released=True)  # what's live
        .provider_branch(branch)
        # Consumer and provider change in the same PR here, so a failing pact must fail
        # the build. In a multi-repo setup you'd include pending (and WIP) pacts instead.
        .exclude_pending()
        .build()
    )
    if os.environ.get("PACT_PUBLISH_VERIFICATION") == "true":
        verifier.set_publish_options(
            version=os.environ["PACT_VERSION"], branch=branch, url=os.environ.get("BUILD_URL")
        )
    return verifier


def verify(verifier: Verifier) -> None:
    """Run provider verification and fail with Pact's own report, not an FFI stack trace."""
    try:
        verifier.verify()
    except RuntimeError:
        pytest.fail(verifier.output(strip_ansi=True), pytrace=False)
