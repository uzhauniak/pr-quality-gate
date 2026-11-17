"""Run Pact contract checks in the right order: consumers publish pacts, then providers verify.

    python quality/run_contracts.py                  # all pairs from deps.yaml
    python quality/run_contracts.py --pairs '[{"consumer": "quotes", "provider": "pricing"}]'

Exit code is non-zero if any consumer test or provider verification fails.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quality.select_tests import all_contract_pairs, load_config  # noqa: E402

PACT_DIR = ROOT / "pacts"


def pytest(*targets: str) -> int:
    args = ["pytest", "--contracts", *targets]
    print("$", " ".join(args), flush=True)
    return subprocess.call([sys.executable, "-m", *args], cwd=ROOT)


def run(pairs: list[dict[str, str]]) -> int:
    if not pairs:
        print("No contract pairs selected.")
        return 0

    for stale in PACT_DIR.glob("*.json"):
        stale.unlink()

    consumers = sorted({p["consumer"] for p in pairs})
    providers = sorted({p["provider"] for p in pairs})

    print(f"\n== 1/2 consumer tests ({', '.join(consumers)}) → generate pacts ==")
    consumer_files = [
        f"services/{p['consumer']}/tests/contract/test_{p['provider']}_consumer.py" for p in pairs
    ]
    if pytest(*consumer_files) != 0:
        return 1

    print(f"\n== 2/2 provider verification ({', '.join(providers)}) ==")
    # Provider tests are parametrized by consumer; select only the pairs in scope.
    provider_tests = [
        f"services/{p['provider']}/tests/contract/test_provider.py"
        f"::test_{p['provider']}_honours_consumer_pact[{p['consumer']}]"
        for p in pairs
    ]
    return pytest(*provider_tests)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pairs", help="JSON list of {consumer, provider}; default: all pairs")
    args = parser.parse_args()
    pairs = json.loads(args.pairs) if args.pairs else all_contract_pairs(load_config())
    return run(pairs)


if __name__ == "__main__":
    sys.exit(main())
