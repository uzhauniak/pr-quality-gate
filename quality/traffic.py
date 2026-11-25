"""Steady synthetic traffic against the deployed API, for the rollback drill.

    python quality/traffic.py --base-url https://... --duration 600 --rps 2

A canary only sees errors if something calls it: 10% of this traffic reaches the new
version while CodeDeploy shifts it, which is what trips the error alarm.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter

BODY = json.dumps({"annual_kwh": 20000, "tariff_code": "FIXED-12M", "region": "NW"}).encode()


def hit(url: str) -> str:
    request = urllib.request.Request(
        url, data=BODY, method="POST", headers={"content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return str(response.status)
    except urllib.error.HTTPError as err:
        return str(err.code)
    except (urllib.error.URLError, TimeoutError):
        return "network"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--duration", type=float, default=600, help="seconds")
    parser.add_argument("--rps", type=float, default=2)
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/prices/quote"
    counts: Counter[str] = Counter()
    started = last_report = time.monotonic()
    while time.monotonic() - started < args.duration:
        counts[hit(url)] += 1
        if time.monotonic() - last_report >= 30:
            print(f"t+{time.monotonic() - started:4.0f}s {dict(counts)}", flush=True)
            last_report = time.monotonic()
        time.sleep(1 / args.rps)
    print(f"done {dict(counts)}", flush=True)


if __name__ == "__main__":
    main()
