"""Root pytest config.

Contract tests are opt-in: a plain `pytest` run gives fast unit + integration feedback,
while consumer/provider tests are orchestrated (consumers first, then providers)
by quality/run_contracts.py, which passes --contracts.
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--contracts",
        action="store_true",
        default=False,
        help="run Pact contract tests (normally invoked via quality/run_contracts.py)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--contracts"):
        return
    skip = pytest.mark.skip(reason="contract test: run via `python quality/run_contracts.py`")
    for item in items:
        if "contract" in item.keywords:
            item.add_marker(skip)
