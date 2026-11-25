"""Publish contract evidence from PactFlow for the README: badges, pacts and a status page.

    python quality/pact_badges.py --out badges

PactFlow serves all of this only to authenticated requests, so the README can't link to
it directly. This writes, into --out:

  *.svg          contract and can-i-deploy badges, as PactFlow renders them
  pacts/*.json   the latest contract for each consumer/provider pair
  STATUS.md      what is in production, the can-i-deploy result per service,
                 links to the pacts and to the CI run that produced it

Reads PACT_BROKER_BASE_URL, PACT_BROKER_TOKEN, PACT_VERSION and, in CI, the GITHUB_* vars.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quality import pact_broker  # noqa: E402

CONTRACTS = [("quotes", "pricing"), ("billing", "quotes")]
SERVICES = ["pricing", "quotes", "billing"]


def get(path: str) -> bytes:
    request = urllib.request.Request(
        os.environ["PACT_BROKER_BASE_URL"].rstrip("/") + path,
        headers={
            "Authorization": f"Bearer {os.environ['PACT_BROKER_TOKEN']}",
            # the default Python-urllib agent is refused by PactFlow's edge
            "User-Agent": "pr-quality-gate-ci/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def badge_paths() -> dict[str, str]:
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


def fetch_badges(out: Path) -> int:
    failed = 0
    for name, path in badge_paths().items():
        try:
            svg = get(path)
        except urllib.error.HTTPError as err:
            print(f"FAIL {name}: HTTP {err.code} {err.read()[:200]!r}")
            failed += 1
            continue
        except urllib.error.URLError as err:
            print(f"FAIL {name}: {err}")
            failed += 1
            continue
        if not svg.lstrip().startswith(b"<svg"):
            print(f"FAIL {name}: not an SVG ({svg[:80]!r})")
            failed += 1
            continue
        (out / name).write_bytes(svg)
        print(f"ok   {name}")
    return failed


def fetch_pacts(out: Path) -> dict[tuple[str, str], dict]:
    (out / "pacts").mkdir(exist_ok=True)
    pacts = {}
    for consumer, provider in CONTRACTS:
        pact = json.loads(get(f"/pacts/provider/{provider}/consumer/{consumer}/latest"))
        pact.pop("_links", None)  # broker navigation links need a login anyway
        pact.pop("_embedded", None)
        (out / "pacts" / f"{consumer}-{provider}.json").write_text(
            json.dumps(pact, indent=2) + "\n", encoding="utf-8"
        )
        pacts[(consumer, provider)] = pact
        print(f"ok   pacts/{consumer}-{provider}.json")
    return pacts


def can_i_deploy(service: str) -> tuple[bool, str]:
    result = pact_broker.broker(
        "can-i-deploy",
        "--pacticipant", service,
        "--version", pact_broker.version(),
        "--to-environment", pact_broker.ENVIRONMENT,
        check=False,
        capture=True,
    )  # fmt: skip
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def status_page(pacts: dict[tuple[str, str], dict]) -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "uzhauniak/pr-quality-gate")
    run = os.environ.get("GITHUB_RUN_ID")
    version = pact_broker.version()
    lines = [
        "# Contract status",
        "",
        f"Generated from PactFlow on {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by the deploy of "
        f"[`{version[:7]}`]({server}/{repo}/commit/{version})"
        + (f" ([CI run]({server}/{repo}/actions/runs/{run}))." if run else "."),
        "",
        "## Contracts",
        "",
        "| Consumer → provider | Interactions | Pact |",
        "|---|---|---|",
    ]
    for (consumer, provider), pact in pacts.items():
        interactions = [i.get("description", "?") for i in pact.get("interactions", [])]
        lines.append(
            f"| {consumer} → {provider} | {'; '.join(interactions)} "
            f"| [pacts/{consumer}-{provider}.json](pacts/{consumer}-{provider}.json) |"
        )
    lines += ["", "## can-i-deploy → production", ""]
    for service in SERVICES:
        ok, output = can_i_deploy(service)
        lines += [
            f"### {service}",
            "",
            f"**{'YES' if ok else 'NO'}**: `{service}` at `{version[:7]}` against what is "
            "recorded as deployed in `production`.",
            "",
            "```text",
            output,
            "```",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    failed = fetch_badges(args.out)
    pacts = fetch_pacts(args.out)
    (args.out / "STATUS.md").write_text(status_page(pacts), encoding="utf-8")
    print("ok   STATUS.md")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
