"""Assemble one Lambda bundle per service under .build/<service>/.

Each bundle holds the service package and the shared lambda_http library. The services
use only the standard library at runtime, so there is nothing to pip-install.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / ".build"
SERVICES = ("pricing", "quotes", "billing")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def main() -> None:
    shutil.rmtree(BUILD, ignore_errors=True)
    for service in SERVICES:
        bundle = BUILD / service
        source = ROOT / "services" / service / "src" / service
        shutil.copytree(source, bundle / service, ignore=IGNORE)
        shutil.copytree(ROOT / "libs" / "lambda_http", bundle / "lambda_http", ignore=IGNORE)
        files = sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob("*.py"))
        print(f"{service}: {', '.join(files)}")


if __name__ == "__main__":
    main()
