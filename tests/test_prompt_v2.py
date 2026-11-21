"""Prompt v2.0: no hidden state, pinned text, scripted LLM sessions, robust parsing."""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np

from mmarena.agents.llm import LLMAgent, prompt_hash
from mmarena.agents.prompt_v2 import render_prompt, render_prompt_parts
from mmarena.agents.registry import make_agent_factory
from mmarena.joint import Regimes
from mmarena.providers.scripted import ScriptedProvider
from mmarena.session_engine import run_session
from mmarena.sessions import SessionObservation, make_session
from mmarena.suite import load_suite

REGIMES = Regimes.of([0.05, 0.5, 0.9])

# Step-0 prompt of each smoke-v2 session (system prompt and both user segments).
SMOKE_V2_PROMPTS = {
    "dice-se2f1c7aa": "7516d637b22eda8f1e860c568cb223290c94dede1078d7ec3ac7108f4adebc88",
    "coin-saafb8a6e": "f5282c4db2d400c5777bb8fb43ad59729f4b81a7e55beec75c06a47f0e10d367",
    "urn-s458e11bd": "41bd230730a580d88d240a3883523b71933c6a526ec41076e1463642ec3e8f72",
}


def _step0(s) -> SessionObservation:
    return SessionObservation(s.spec, s.id, 0, 0, 0, (), (), (), 0, 0.0, True, True)


def test_step0_prompts_are_pinned() -> None:
    got = {}
    for s in load_suite("smoke-v2").sessions():
        system, parts = render_prompt_parts(_step0(s))
        got[s.id] = prompt_hash(system, parts)
    assert got == SMOKE_V2_PROMPTS


def _prompts(regime: int, quote) -> list[tuple[str, str]]:
    s = make_session("dice", 7311, 0.7, REGIMES, regime, 3, "mixed")
    provider = ScriptedProvider(quote)
    run_session(s, LLMAgent(provider, renderer=render_prompt_parts), 4)
    return provider.calls


def test_prompt_is_identical_across_regimes_at_the_same_public_state() -> None:
    """With no quotes there is no flow, so the public states coincide across regimes; so must
    every prompt. Outcomes enter only through reveals and settlements."""
    none = '{"bid": null, "ask": null}'
    runs = [_prompts(k, none) for k in range(3)]
    assert len(runs[0]) == 12
    assert runs[0] == runs[1] == runs[2]


def test_prompt_states_the_rules_without_hints_or_tiers() -> None:
    s = list(load_suite("smoke-v2").sessions())[1]
    system, user = render_prompt(_step0(s))
    text = system + user
    assert "{0.05, 0.5, 0.9}, each with probability 1/3" in text
    assert "standard deviation 9.3, the same in every round" in text
    for leak in ("tier", "mixed", "open", "regime", "learn", "explore", "booked", "profit so far"):
        assert leak not in text.lower().replace("opens", ""), leak
    assert "trading history implies about alpha" not in text


def test_history_shows_raw_rows_reveals_and_settlements() -> None:
    s = make_session("dice", 7311, 0.7, REGIMES, 1, 3, "mixed")
    seen: list[SessionObservation] = []

    class Rec:
        name = "rec"

        def reset(self, spec) -> None:
            pass

        def act(self, obs):
            from mmarena.agents.base import Quote

            seen.append(obs)
            g = obs.game
            return Quote(g.prior_mean - 0.3 * g.prior_std, g.prior_mean + 0.3 * g.prior_std)

    tr = run_session(s, Rec(), 0)
    _, user = render_prompt(seen[-1])
    for r in tr["rounds"][:-1]:
        assert f"Settlement value: {r['value']:g}" in user
        for x in r["revealed"]:
            assert f"Revealed before stage {x['stage'] + 1}: {x['name']} = {x['value']:g}" in user
    assert "Round 3 (this round)" in user
    hidden = tr["rounds"][0]["hidden"]
    unrevealed = [n for n in hidden if n not in {x["name"] for x in tr["rounds"][0]["revealed"]}]
    for name in unrevealed:
        assert f"{name} =" not in user
    rows = [ln for ln in user.splitlines() if ln.count(" | ") == 4 and ln[0].isdigit()]
    assert len(rows) == len(seen) - 1


def test_scripted_llm_plays_a_full_session_through_the_registry() -> None:
    factory = make_agent_factory('scripted:{"bid": 10, "ask": 25}', suite_format=2)
    s = list(load_suite("smoke-v2").sessions())[0]
    agent = factory()
    tr = run_session(s, agent, 0)
    assert tr["status"] == "ok" and len(tr["steps"]) == 8
    assert all(step["invalid"] is None for step in tr["steps"])
    assert tr["provenance"]["prompt_sha256"] == SMOKE_V2_PROMPTS[s.id]
    assert len({step["info"]["prompt_sha256"] for step in tr["steps"]}) == 8


def test_no_reply_beats_the_references() -> None:
    """Adversarial replies: after parsing and snapping, no quote has a higher ev than the
    learner or a higher ev_alpha than the oracle at the same state."""
    rng = np.random.default_rng(11)
    s = make_session("coin", 7400, 0.7, REGIMES, 0, 3, "mixed")
    g = s.game

    def reply(system: str, user: str) -> str:
        kind = int(rng.integers(8))
        mu, sd = g.prior_mean, g.prior_std
        b, a = mu + rng.normal(0, 2) * sd, mu + rng.normal(0, 2) * sd
        return [
            json.dumps({"bid": b, "ask": a}),
            json.dumps({"bid": None, "ask": a}),
            json.dumps({"bid": b, "ask": None}),
            '{"bid": 1e308, "ask": 1e308}',
            '{"bid": -1e12, "ask": 1e12}',
            f'{{"bid": "{b:.3f}", "ask": "{a:.3f}"}}',
            "I will not quote. {bid: NaN, ask: Infinity}",
            f'first {{"bid": 0, "ask": 1}} then {{"bid": {min(a, b)}, "ask": {max(a, b)}}}',
        ][kind]

    for seed in range(4):
        tr = run_session(s, LLMAgent(ScriptedProvider(reply), renderer=render_prompt_parts), seed)
        assert tr["status"] == "ok"
        for step in tr["steps"]:
            assert step["ev"] <= step["bayes_ev"] + 1e-9
            assert step["ev_alpha"] <= step["oracle_ev_alpha"] + 1e-9
            for side in ("bid", "ask"):
                assert step[side] is None or math.isfinite(step[side])


def test_cache_salt_is_per_session() -> None:
    import tempfile
    from pathlib import Path

    from mmarena.cache import CachedProvider, ResponseCache

    s = list(load_suite("smoke-v2").sessions())[0]
    with tempfile.TemporaryDirectory() as d:
        provider = CachedProvider(ScriptedProvider('{"bid": 1, "ask": 2}'), ResponseCache(d))
        run_session(s, LLMAgent(provider, renderer=render_prompt_parts), 0)
        keys = sorted(p.stem for p in Path(d).rglob("*.json"))
    assert len(keys) == 8
    digest = hashlib.sha256("\n".join(keys).encode()).hexdigest()
    assert digest == "f5050ff04053cc10b2183d001b4e51166ea997818b115f37a08ba81890f18bf7"
