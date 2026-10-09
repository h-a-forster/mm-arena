"""LLMAgent with a scripted provider, end to end through the engine."""

from __future__ import annotations

import json
import re

import pytest

from mmarena.agents.base import AgentError, Observation
from mmarena.agents.llm import LLMAgent
from mmarena.cache import CachedProvider, ResponseCache
from mmarena.engine import run_episode
from mmarena.games import make_game
from mmarena.providers.base import Completion
from mmarena.providers.scripted import ScriptedProvider


@pytest.fixture(scope="module")
def game():
    return make_game("dice", 11, "perturbed")


def _obs(game) -> Observation:
    return Observation(game, 0, 0, (), (), 0, 0.0, True, True)


def test_quote_and_info(game):
    agent = LLMAgent(ScriptedProvider('thinking...\n{"bid": 10, "ask": 12}'), name="t")
    q = agent.act(_obs(game))
    assert (q.bid, q.ask) == (10.0, 12.0)
    assert q.info["repairs"] == 0
    assert q.info["model"] == "scripted"
    assert q.info["raw"].endswith('{"bid": 10, "ask": 12}')
    assert q.info["usage"]["input_tokens"] > 0
    assert q.info["cost_usd"] == 0.0
    assert q.info["cached"] is False


def test_repair_then_success(game):
    prov = ScriptedProvider(["bid 10 ask 12", '{"bid": 10, "ask": 12}'])
    q = LLMAgent(prov, repair_attempts=1).act(_obs(game))
    assert (q.bid, q.ask) == (10.0, 12.0)
    assert q.info["repairs"] == 1
    assert q.info["raw_rejected"] == ["bid 10 ask 12"]
    assert "could not be used" in prov.calls[1][1]
    assert "bid 10 ask 12" in prov.calls[1][1]
    # The repair keeps the static game text at the front.
    assert prov.calls[1][1].startswith(prov.calls[0][1].split("Current state")[0])


def test_failure_raises_with_info(game):
    prov = ScriptedProvider("no idea")
    with pytest.raises(AgentError) as ei:
        LLMAgent(prov, repair_attempts=2).act(_obs(game))
    info = ei.value.info
    assert info["repairs"] == 2
    assert info["raw"] == "no idea"
    assert "parse_error" in info
    assert len(prov.calls) == 3


def test_no_repair(game):
    prov = ScriptedProvider("no idea")
    with pytest.raises(AgentError):
        LLMAgent(prov, repair_attempts=0).act(_obs(game))
    assert len(prov.calls) == 1


def test_refusal_is_agent_error(game):
    class Refuser(ScriptedProvider):
        def complete(self, system, user, *, max_tokens):
            c = super().complete(system, user, max_tokens=max_tokens)
            c.stop_reason = "refusal"
            return c

    with pytest.raises(AgentError, match="refused"):
        LLMAgent(Refuser(""), repair_attempts=3).act(_obs(game))


def test_raw_truncated(game):
    text = "x" * 10_000 + '{"bid": 1, "ask": 2}'
    q = LLMAgent(ScriptedProvider(text)).act(_obs(game))
    assert len(q.info["raw"]) < 2200
    assert q.info["raw"].endswith('{"bid": 1, "ask": 2}')


def _mid_policy(system: str, user: str) -> str:
    """Quote around the midpoint of the last history row, or 10/14 at the start."""
    rows = re.findall(r"^\d+ \| \d+ \| (\S+) \| (\S+) \|", user, re.M)
    bid, ask = (10.0, 14.0)
    if rows and rows[-1][0] != "-" and rows[-1][1] != "-":
        bid, ask = float(rows[-1][0]) - 0.5, float(rows[-1][1]) + 0.5
    return json.dumps({"bid": bid, "ask": ask})


def test_engine_integration(game):
    agent = LLMAgent(ScriptedProvider(_mid_policy), name="scripted-mid")
    trace = run_episode(game, agent, seed=4)
    assert trace["status"] == "ok"
    assert trace["agent"] == "scripted-mid"
    assert all(s["invalid"] is None for s in trace["steps"])
    assert trace["steps"][0]["bid_quoted"] == 10.0
    assert all("usage" in s["info"] for s in trace["steps"])


def test_engine_records_invalid_with_raw(game):
    agent = LLMAgent(ScriptedProvider("garbage"), repair_attempts=0)
    trace = run_episode(game, agent, seed=1)
    assert trace["status"] == "ok"
    s = trace["steps"][0]
    assert s["invalid"] == "format"
    assert s["info"]["raw"] == "garbage"
    assert s["bid"] is None and s["ask"] is None


class _Counting:
    name = "counting"
    model = "m"
    options: dict = {}

    def __init__(self):
        self.n = 0

    def complete(self, system, user, *, max_tokens):
        self.n += 1
        return Completion(text=f'{{"bid": {self.n}, "ask": {self.n + 1}}}', model="m")


def test_cache_keys_on_episode(tmp_path, game):
    from dataclasses import replace

    inner = _Counting()
    prov = CachedProvider(inner, ResponseCache(tmp_path))
    obs = [replace(_obs(game), episode_seed=s) for s in range(3)]
    first = [LLMAgent(prov).act(o).bid for o in obs]
    assert first == [1.0, 2.0, 3.0]  # identical prompts in different episodes: separate samples
    # Same episode again (re-run, resume, any thread order): replayed from disk, in any order.
    prov2 = CachedProvider(inner, ResponseCache(tmp_path))
    quotes = [LLMAgent(prov2).act(o) for o in reversed(obs)]
    assert [q.bid for q in quotes] == first[::-1]
    assert all(q.info["cached"] for q in quotes)
    assert inner.n == 3
    # A new episode is a new sample.
    assert LLMAgent(prov2).act(replace(obs[0], episode_seed=7)).bid == 4.0
