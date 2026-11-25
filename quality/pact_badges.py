"""Download contract and can-i-deploy badges from PactFlow (they need the API token).

    python quality/pact_badges.py --out badges

Reads PACT_BROKER_BASE_URL and PACT_BROKER_TOKEN. Writes one SVG per badge.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONTRACTS = [("quotes", "pricing"), ("billing", "quotes")]
SERVICES = ["pricing", "quotes", "billing"]


def badges() -> dict[str, str]:
    paths = {}
    for consumer, provider in CONTRACTS:
        label = urllib.parse.quote(f"{consumer} → {provider}")
        paths[f"contract-{consumer}-{provider}.svg"] = (
            f"/pacts/provider/{provider}/consumer/{consumer}/latest/badge.svg?label={label}"
        )
    for service in SERVICES:
        paths[f"can-i-deploy-{service}.svg"] = (
            f"/pacticipants/{service}/branches/main/latest-version"
            f"/can-i-deploy/to-environment/production/badge?label={service}"
        )
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    base = os.environ["PACT_BROKER_BASE_URL"].rstrip("/")
    token = os.environ["PACT_BROKER_TOKEN"]
    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, path in badges().items():
        request = urllib.request.Request(
            base + path, headers={"Authorization": f"Bearer {token}", "Accept": "image/svg+xml"}
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                svg = response.read()
        except urllib.error.URLError as err:
            print(f"FAIL {name}: {err}")
            failed += 1
            continue
        if not svg.lstrip().startswith(b"<svg"):
            print(f"FAIL {name}: not an SVG ({svg[:80]!r})")
            failed += 1
            continue
        (args.out / name).write_bytes(svg)
        print(f"ok   {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
