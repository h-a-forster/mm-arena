"""Agent spec parsing and factories."""

from __future__ import annotations

import pytest

from mmarena.agents.baselines import BASELINES
from mmarena.agents.llm import LLMAgent
from mmarena.agents.registry import list_agent_kinds, make_agent_factory, parse_spec
from mmarena.cache import CachedProvider


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("anthropic:claude-sonnet-5-5", ("anthropic", "claude-sonnet-5-5", None, None)),
        ("openai:gpt-5.1", ("openai", "gpt-5.1", None, None)),
        (
            "openai:llama3.1@http://localhost:11434/v1",
            ("openai", "llama3.1", "http://localhost:11434/v1", None),
        ),
        (
            "openai:qwen3:8b@http://localhost:8000/v1@high",
            ("openai", "qwen3:8b", "http://localhost:8000/v1", "high"),
        ),
        ("claude-cli:haiku", ("claude-cli", "haiku", None, None)),
        ("claude-cli:sonnet@low", ("claude-cli", "sonnet", None, "low")),
        ('scripted:{"bid": 1, "ask": 2}', ("scripted", '{"bid": 1, "ask": 2}', None, None)),
    ],
)
def test_parse_spec(spec, expected):
    p = parse_spec(spec)
    assert (p["kind"], p["model"], p["base_url"], p["effort"]) == expected


@pytest.mark.parametrize("spec", ["gpt", "foo:bar", "anthropic:", "claude-cli:x@http://h/v1"])
def test_parse_spec_errors(spec):
    with pytest.raises(ValueError):
        parse_spec(spec)


def test_baselines():
    for name in BASELINES:
        agent = make_agent_factory(name, cache=True, max_tokens=100, effort="low")()
        assert agent.name == name
    assert make_agent_factory("bayes", name="ref")().name == "ref"


def test_llm_factory_names_and_cache(tmp_path):
    f = make_agent_factory("claude-cli:sonnet", effort="low", cache=str(tmp_path))
    a, b = f(), f()
    assert isinstance(a, LLMAgent) and a is not b
    assert a.name == "claude-cli:sonnet@low"
    assert isinstance(a.provider, CachedProvider)
    assert a.provider is b.provider  # shared, thread-safe
    assert a.provider.inner.effort == "low"
    assert make_agent_factory("claude-cli:sonnet@low")().name == "claude-cli:sonnet@low"
    g = make_agent_factory("anthropic:claude-haiku-5-5", cache=False, name="h", max_tokens=99)()
    assert g.name == "h" and g.max_tokens == 99
    assert not isinstance(g.provider, CachedProvider)
    o = make_agent_factory("openai:llama3.1@http://localhost:11434/v1", cache=False)()
    assert o.provider.base_url == "http://localhost:11434/v1"
    assert o.name == "openai:llama3.1@http://localhost:11434/v1"


def test_factory_errors():
    with pytest.raises(ValueError, match="unknown option"):
        make_agent_factory("anthropic:claude-opus-5-5", temperature=0.2)
    with pytest.raises(ValueError, match="conflicts"):
        make_agent_factory("claude-cli:sonnet@low", effort="high")
    with pytest.raises(ValueError):
        make_agent_factory("claude-cli:sonnet", effort="turbo")


def test_scripted_factory_runs():
    from mmarena.engine import run_episode
    from mmarena.games import make_game

    agent = make_agent_factory('scripted:{"bid": 1, "ask": 2}', cache=True)()
    trace = run_episode(make_game("coin", 2, "classic"), agent, seed=0)
    assert trace["status"] == "ok"
    assert trace["agent"] == 'scripted:{"bid": 1, "ask": 2}'


def test_list_agent_kinds():
    kinds = dict(list_agent_kinds())
    assert "bayes" in kinds and "claude-cli:MODEL" in kinds
