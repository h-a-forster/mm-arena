import pytest
from conftest import ScriptedAgent, tiny_game

from mmarena.agents.base import Quote
from mmarena.engine import run_episode
from mmarena.metrics import _step_usage, episode_metrics
from mmarena.pricing import PRICES, list_cost, price_for


def test_price_lookup():
    assert price_for("claude-opus-5-5") == PRICES["claude-opus-5-5"]
    assert price_for("claude-haiku-4-5-20251001") == PRICES["claude-haiku-4-5"]
    # The longest base id wins: an Opus 5.5 snapshot is not priced as Opus 5.
    assert price_for("claude-opus-5-5-20261001") == PRICES["claude-opus-5-5"]
    assert price_for("gpt-5.1") is None
    assert price_for(None) is None


def test_list_cost_cache_write_ttl():
    usage = {"input_tokens": 10, "output_tokens": 100, "cache_write_tokens": 1000}
    five = (10 * 4 + 100 * 20 + 1000 * 5) / 1e6
    hour = (10 * 4 + 100 * 20 + 1000 * 8) / 1e6
    assert list_cost("claude-opus-5-5", usage) == pytest.approx(five)
    assert list_cost("claude-opus-5-5", usage, default_write_ttl="1h") == pytest.approx(hour)
    split = {**usage, "cache_write_1h_tokens": 400}
    mixed = (10 * 4 + 100 * 20 + 600 * 5 + 400 * 8) / 1e6
    # A recorded split overrides the default.
    assert list_cost("claude-opus-5-5", split, default_write_ttl="1h") == pytest.approx(mixed)
    assert list_cost("unknown", usage) is None


def test_step_cost_prefers_list_price():
    info = {
        "model": "claude-haiku-5-5",
        "usage": {"input_tokens": 1000, "output_tokens": 1000},
        "cost_usd": 0.024,  # a provider figure at the wrong rates
    }
    tokens, cost = _step_usage(info)
    assert tokens == 2000
    assert cost == pytest.approx((1000 * 0.10 + 1000 * 0.50) / 1e6)
    # Unknown model: the reported cost is kept.
    assert _step_usage({**info, "model": "other"})[1] == 0.024


def test_claude_cli_traces_price_writes_at_one_hour():
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_write_tokens": 1_000_000}
    agent = ScriptedAgent(lambda obs: Quote(2.0, 8.0, {"model": "claude-opus-5-5", "usage": usage}))
    trace = run_episode(tiny_game(), agent, 0)
    trace["agent"] = "claude-cli:claude-opus-5-5@low"
    assert episode_metrics(trace).cost_usd == pytest.approx(3 * 8.0)
    trace["agent"] = "anthropic:claude-opus-5-5"
    assert episode_metrics(trace).cost_usd == pytest.approx(3 * 5.0)
