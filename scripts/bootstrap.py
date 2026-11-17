"""Create the git history for this repo: `main` plus one branch per demo patch.

    python scripts/bootstrap.py --remote git@personal:<login>/pr-quality-gate.git

Commits are made with *your* local git identity (user.name / user.email), which the
script shows and asks you to confirm first. Nothing is pushed.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / "demo" / "patches"
# Shipped outside .github/ (some sync tools refuse to write workflow files); moved in on bootstrap.
WORKFLOW_SRC = ROOT / "ci" / "quality-gate.yml"
WORKFLOW_DST = ROOT / ".github" / "workflows" / "quality-gate.yml"


def git(*args: str, capture: bool = False) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else ""


def config_value(key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--get", key], cwd=ROOT, text=True, capture_output=True
    )
    return result.stdout.strip()


def subject(patch: Path) -> str:
    first = patch.read_text(encoding="utf-8").splitlines()[0]
    return first.removeprefix("Subject: ").strip()


def branch_name(patch: Path) -> str:
    # 01-low-risk.patch -> demo/low-risk
    return "demo/" + patch.stem.split("-", 1)[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--remote", help="origin URL, e.g. git@personal:<login>/<repo>.git")
    parser.add_argument("--yes", action="store_true", help="skip the identity confirmation")
    args = parser.parse_args()

    if (ROOT / ".git").exists():
        has_commits = (
            subprocess.run(
                ["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=ROOT, capture_output=True
            ).returncode
            == 0
        )
        if has_commits:
            print("This repository already has commits; nothing to do.")
            return 1
    else:
        git("init", "-q", "-b", "main")
    name, email = config_value("user.name"), config_value("user.email")
    if not name or not email:
        print("git user.name / user.email are not set. Set them first, e.g.:")
        print('  git config --global user.name "Your Name"')
        print('  git config --global user.email "you@example.com"')
        return 1
    print(f"Commits will be authored as: {name} <{email}>")
    if not args.yes and input("Continue? [y/N] ").strip().lower() != "y":
        print("Aborted. Set the identity for this repo only, then run the script again:")
        print('  git config user.name "Your Name"')
        print("  git config user.email <address>")
        return 1

    if WORKFLOW_SRC.exists() and not WORKFLOW_DST.exists():
        WORKFLOW_DST.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(WORKFLOW_SRC, WORKFLOW_DST)
        WORKFLOW_SRC.parent.rmdir()
        print(f"  moved CI workflow to {WORKFLOW_DST.relative_to(ROOT).as_posix()}")

    git("add", "-A")
    git("commit", "-q", "-m", "Risk-aware PR quality gate: test selection + Pact contracts")

    for patch in sorted(PATCHES.glob("*.patch")):
        branch = branch_name(patch)
        git("checkout", "-q", "-b", branch, "main")
        git("apply", str(patch))
        git("commit", "-q", "-am", subject(patch))
        print(f"  created {branch}: {subject(patch)}")
    git("checkout", "-q", "main")

    if args.remote:
        git("remote", "add", "origin", args.remote)

    branches = [branch_name(p) for p in sorted(PATCHES.glob("*.patch"))]
    print("\nDone. Next steps:")
    if not args.remote:
        print("  git remote add origin git@personal:<login>/pr-quality-gate.git")
    print("  git push -u origin main")
    for branch in branches:
        print(f"  git push -u origin {branch}")
    print("Then open one PR per demo branch (base: main), e.g.:")
    print(f"  gh pr create --base main --head {branches[0]} --fill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
