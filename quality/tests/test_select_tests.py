"""The selector decides what *not* to test, so it gets tests of its own."""

import pytest

from quality.select_tests import build_plan, load_config


@pytest.fixture(scope="module")
def config():
    return load_config()


def pairs(plan):
    return {(p["consumer"], p["provider"]) for p in plan.contracts}


def test_leaf_service_change_tests_only_itself(config):
    plan = build_plan(["services/billing/src/billing/invoicing.py"], config)

    assert not plan.run_full
    assert plan.services == ["billing"]
    assert pairs(plan) == {("billing", "quotes")}  # billing's own consumer pact
    assert plan.skipped == ["pricing", "quotes"]


def test_provider_change_pulls_in_direct_consumers_and_their_pacts(config):
    plan = build_plan(["services/pricing/src/pricing/engine.py"], config)

    assert plan.services == ["pricing", "quotes"]
    assert pairs(plan) == {("quotes", "pricing")}
    assert plan.skipped == ["billing"]
    assert "quotes consumes pricing" in plan.reasons


def test_middle_service_change_checks_both_sides(config):
    plan = build_plan(["services/quotes/src/quotes/service.py"], config)

    assert plan.services == ["billing", "quotes"]
    assert pairs(plan) == {("quotes", "pricing"), ("billing", "quotes")}


def test_openapi_change_counts_as_service_change(config):
    plan = build_plan(["services/pricing/openapi.yaml"], config)

    assert plan.services == ["pricing", "quotes"]


def test_docs_only_change_runs_nothing(config):
    plan = build_plan(["README.md", "services/pricing/README.md", "docs/plan.md"], config)

    assert plan.services == []
    assert plan.contracts == []
    assert plan.reasons == ["no code changes"]


@pytest.mark.parametrize(
    "path",
    ["libs/lambda_http/router.py", "pyproject.toml", ".github/workflows/quality-gate.yml"],
)
def test_shared_change_runs_everything(config, path):
    plan = build_plan(["services/billing/src/billing/handler.py", path], config)

    assert plan.run_full
    assert plan.services == ["billing", "pricing", "quotes"]
    assert len(plan.contracts) == 2


def test_unknown_path_fails_safe_to_full_run(config):
    plan = build_plan(["infra/terraform/main.tf"], config)

    assert plan.run_full
    assert "not in dependency model" in plan.reasons[0]
