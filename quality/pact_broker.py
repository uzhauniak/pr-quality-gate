"""Thin wrapper over the Pact Broker CLI (`pact broker ...` from the pact-python-cli package).

    python quality/pact_broker.py publish
    python quality/pact_broker.py setup                      # environment + main branches
    python quality/pact_broker.py can-i-deploy pricing quotes
    python quality/pact_broker.py record-deployment billing pricing quotes

Reads PACT_BROKER_BASE_URL / PACT_BROKER_TOKEN, plus PACT_VERSION and PACT_BRANCH
(defaulting to the current git commit and branch). Works against PactFlow or a
self-hosted broker.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = "production"
MAIN_BRANCH = "main"


def enabled() -> bool:
    return bool(os.environ.get("PACT_BROKER_BASE_URL") and os.environ.get("PACT_BROKER_TOKEN"))


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def version() -> str:
    return os.environ.get("PACT_VERSION") or _git("rev-parse", "HEAD")


def branch() -> str:
    return os.environ.get("PACT_BRANCH") or _git("rev-parse", "--abbrev-ref", "HEAD")


def _cli() -> str:
    exe = shutil.which("pact") or shutil.which("pact", path=str(Path(sys.executable).parent))
    if not exe:
        raise SystemExit("`pact` CLI not found: pip install -r requirements-dev.txt")
    return exe


def broker(
    *args: str, check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    cmd = [_cli(), "broker", *args]
    print("$ pact broker", " ".join(args), flush=True)
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=capture)
    if capture and result.stdout:
        print(result.stdout, end="")
    if capture and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def publish() -> None:
    pacts = sorted((ROOT / "pacts").glob("*.json"))
    if not pacts:
        print("no pact files to publish")
        return
    args = ["publish", *(str(p.relative_to(ROOT)) for p in pacts)]
    args += ["--consumer-app-version", version(), "--branch", branch()]
    if url := os.environ.get("BUILD_URL"):
        args += ["--build-url", url]
    broker(*args)


def setup(services: list[str]) -> None:
    """Idempotent: make sure the environment exists and main branches are declared."""
    listing = broker("list-environments", capture=True).stdout
    if not re.search(rf"\b{ENVIRONMENT}\b", listing):
        broker("create-environment", "--name", ENVIRONMENT, "--production")
    for service in services:
        broker("create-or-update-pacticipant", "--name", service, "--main-branch", MAIN_BRANCH)


def can_i_deploy(services: list[str]) -> int:
    failed = []
    for service in services:
        result = broker(
            "can-i-deploy",
            "--pacticipant", service,
            "--version", version(),
            "--to-environment", ENVIRONMENT,
            "--retry-while-unknown", "6",
            "--retry-interval", "10",
            check=False,
        )  # fmt: skip
        if result.returncode != 0:
            failed.append(service)
    if failed:
        print(f"\ncan-i-deploy: NO for {', '.join(failed)} → {ENVIRONMENT}")
        return 1
    print(f"\ncan-i-deploy: YES for {', '.join(services)} → {ENVIRONMENT}")
    return 0


def record_deployment(services: list[str]) -> None:
    for service in services:
        broker(
            "record-deployment",
            "--pacticipant", service,
            "--version", version(),
            "--environment", ENVIRONMENT,
        )  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("publish")
    for name in ("setup", "can-i-deploy", "record-deployment"):
        sub.add_parser(name).add_argument("services", nargs="*")
    args = parser.parse_args(argv)

    if not enabled():
        print("PACT_BROKER_BASE_URL / PACT_BROKER_TOKEN not set: broker step skipped")
        return 0
    if args.command == "publish":
        publish()
    elif args.command == "setup":
        setup(args.services)
    elif args.command == "can-i-deploy":
        return can_i_deploy(args.services) if args.services else 0
    else:
        record_deployment(args.services)
    return 0


if __name__ == "__main__":
    sys.exit(main())
