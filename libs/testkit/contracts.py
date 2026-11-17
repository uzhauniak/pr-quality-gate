"""Shared Pact conventions: one pacts/ folder at the repo root, `<consumer>-<provider>.json`."""

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


def verify(verifier: Verifier) -> None:
    """Run provider verification and fail with Pact's own report, not an FFI stack trace."""
    try:
        verifier.verify()
    except RuntimeError:
        pytest.fail(verifier.output(strip_ansi=True), pytrace=False)
