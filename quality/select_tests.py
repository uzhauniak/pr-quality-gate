"""Decide which test suites and contracts a change needs, from the dependency model in deps.yaml.

    python quality/select_tests.py --base origin/main     # diff against a base ref
    python quality/select_tests.py --files a.py b.py      # explicit file list
    python quality/select_tests.py --full                 # everything (e.g. push to main)

Prints the plan as JSON. In GitHub Actions, --github writes step outputs and a job summary.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "quality" / "deps.yaml"


@dataclass
class Plan:
    run_full: bool = False
    services: list[str] = field(default_factory=list)
    contracts: list[dict[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def all_contract_pairs(config: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"consumer": consumer, "provider": provider}
        for provider, spec in config["services"].items()
        for consumer in spec.get("consumers", [])
    ]


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def full_plan(config: dict[str, Any], reason: str, files: list[str] | None = None) -> Plan:
    return Plan(
        run_full=True,
        services=sorted(config["services"]),
        contracts=all_contract_pairs(config),
        reasons=[reason],
        changed_files=files or [],
    )


def build_plan(files: list[str], config: dict[str, Any]) -> Plan:
    services: dict[str, Any] = config["services"]
    changed: set[str] = set()
    reasons: list[str] = []

    for path in files:
        if _matches(path, config.get("ignore", [])):
            continue
        if _matches(path, config.get("shared", [])):
            return full_plan(config, f"shared path changed: {path}", files)
        owner = next((name for name, s in services.items() if _matches(path, s["paths"])), None)
        if owner is None:
            return full_plan(config, f"path not in dependency model: {path}", files)
        changed.add(owner)

    if not changed:
        return Plan(skipped=sorted(services), reasons=["no code changes"], changed_files=files)

    selected = set(changed)
    for name in sorted(changed):
        reasons.append(f"{name} changed")
        for consumer in services[name].get("consumers", []):
            if consumer not in changed:
                reasons.append(f"{consumer} consumes {name}")
            selected.add(consumer)

    contracts = [
        pair
        for pair in all_contract_pairs(config)
        if pair["consumer"] in changed or pair["provider"] in changed
    ]
    return Plan(
        services=sorted(selected),
        contracts=contracts,
        skipped=sorted(set(services) - selected),
        reasons=reasons,
        changed_files=files,
    )


def changed_files(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def summary_markdown(plan: Plan) -> str:
    def names(items: list[str]) -> str:
        return ", ".join(f"`{i}`" for i in items) or "—"

    pairs = [f"`{p['consumer']} → {p['provider']}`" for p in plan.contracts]
    lines = [
        "## Test selection plan",
        "",
        f"**Mode:** {'full run' if plan.run_full else 'targeted run'}",
        "",
        "| | |",
        "|---|---|",
        f"| Test suites | {names(plan.services)} |",
        f"| Contracts | {', '.join(pairs) or '—'} |",
        f"| Skipped | {names(plan.skipped)} |",
        "",
        "**Why:**",
        *[f"- {reason}" for reason in plan.reasons],
        "",
        f"<details><summary>{len(plan.changed_files)} changed file(s)</summary>",
        "",
        *[f"- `{f}`" for f in plan.changed_files],
        "",
        "</details>",
    ]
    return "\n".join(lines) + "\n"


def write_github(plan: Plan) -> None:
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        out.write(f"services={json.dumps(plan.services)}\n")
        out.write(f"contracts={json.dumps(plan.contracts)}\n")
        out.write(f"run_full={str(plan.run_full).lower()}\n")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write(summary_markdown(plan))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base", help="git ref to diff against, e.g. origin/main")
    source.add_argument("--files", nargs="*", help="explicit list of changed files")
    source.add_argument("--full", action="store_true", help="select everything")
    parser.add_argument("--github", action="store_true", help="write GitHub Actions outputs")
    parser.add_argument("--markdown", action="store_true", help="print the summary table")
    args = parser.parse_args(argv)

    config = load_config()
    if args.full:
        plan = full_plan(config, "full run requested")
    else:
        files = args.files if args.files is not None else changed_files(args.base)
        plan = build_plan(files, config)

    print(summary_markdown(plan) if args.markdown else json.dumps(asdict(plan), indent=2))
    if args.github:
        write_github(plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
