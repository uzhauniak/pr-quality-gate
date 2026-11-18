"""Risk policy: the LLM can raise the rating, never lower it below the deterministic floor."""

import json
from types import SimpleNamespace

import pytest

from quality.risk import assess, comment_markdown, escalate, heuristic, mutation_targets
from quality.select_tests import build_plan, load_config

ENGINE = "services/pricing/src/pricing/engine.py"
INVOICING = "services/billing/src/billing/invoicing.py"


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def policy(config):
    return config["risk"]


class FakeLLM:
    """Stands in for anthropic.Anthropic: records the call, returns a JSON text block."""

    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.calls = answer, error, []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        thinking = SimpleNamespace(type="thinking", thinking="...")
        text = SimpleNamespace(type="text", text=json.dumps(self.answer))
        return SimpleNamespace(content=[thinking, text])


def llm(risk, reasons=("because",), checks=()):
    return FakeLLM({"risk": risk, "reasons": list(reasons), "suggested_checks": list(checks)})


def run(files, client, config, policy):
    return assess(files, "diff", build_plan(files, config), policy, client)


def test_llm_rating_used_when_no_floor_applies(config, policy):
    result = run([INVOICING], llm("low", ["log wording only"]), config, policy)

    assert result.risk == "low"
    assert result.source == "llm"
    assert result.reasons == ["log wording only"]


def test_llm_cannot_lower_below_floor(config, policy):
    result = run([ENGINE], llm("low"), config, policy)

    assert result.risk == "high"
    assert result.source == "llm+floor"
    assert result.llm_risk == "low"
    assert any("engine.py" in r for r in result.floor_reasons)


def test_llm_can_raise_above_floor(config, policy):
    assert run([INVOICING], llm("high"), config, policy).risk == "high"


def test_llm_output_is_schema_constrained_and_diff_marked_untrusted(config, policy):
    client = llm("low")
    run([INVOICING], client, config, policy)

    call = client.calls[0]
    output_format = call["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["schema"]["properties"]["risk"]["enum"] == ["low", "medium", "high"]
    assert "untrusted" in call["system"]
    assert "<diff>" in call["messages"][0]["content"]


@pytest.mark.parametrize(
    "client",
    [
        FakeLLM(error=TimeoutError("slow")),
        FakeLLM({"risk": "catastrophic", "reasons": ["?"]}),
        FakeLLM({"risk": "low", "reasons": []}),
    ],
)
def test_llm_failure_or_bad_output_falls_back_to_rules(client, config, policy):
    result = run([ENGINE], client, config, policy)

    assert result.source == "heuristic"
    assert result.risk == "high"
    assert result.llm_error


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ([ENGINE], "high"),
        (["services/pricing/openapi.yaml"], "high"),
        (["services/quotes/src/quotes/pricing_client.py"], "high"),
        ([INVOICING], "medium"),
        (["services/billing/tests/unit/test_invoicing.py", "README.md"], "low"),
    ],
)
def test_rules_without_llm(files, expected, policy):
    assert heuristic(files, policy).risk == expected


def test_high_risk_escalates_to_full_run(config, policy):
    plan = build_plan([ENGINE], config)
    result = run([ENGINE], None, config, policy)

    escalated = escalate(plan, result, config)

    assert plan.services == ["pricing", "quotes"]
    assert escalated.run_full
    assert escalated.services == ["billing", "pricing", "quotes"]
    assert len(escalated.contracts) == 2
    assert escalated.changed == ["pricing"]


def test_lower_risk_keeps_targeted_plan(config, policy):
    plan = build_plan([INVOICING], config)
    assert escalate(plan, run([INVOICING], llm("low"), config, policy), config) is plan


def test_mutation_targets_are_changed_source_files_only():
    files = [ENGINE, "services/pricing/tests/unit/test_engine.py", "services/pricing/openapi.yaml"]
    assert mutation_targets(files) == [ENGINE]


def test_comment_explains_floor_override(config, policy):
    plan = build_plan([ENGINE], config)
    result = run([ENGINE], llm("low", ["looks cosmetic"], ["add a boundary test"]), config, policy)

    text = comment_markdown(result, escalate(plan, result, config), [ENGINE])

    assert "HIGH" in text
    assert "raised by policy" in text
    assert "- [ ] add a boundary test" in text
    assert "mutation testing" in text
