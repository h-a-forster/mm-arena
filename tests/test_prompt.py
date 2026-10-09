"""Prompt rendering and reply parsing."""

from __future__ import annotations

import pytest

from mmarena.agents.base import AgentError, Observation
from mmarena.agents.prompt import (
    parse_quote,
    render_prompt,
    render_prompt_parts,
    render_repair,
)
from mmarena.engine import run_episode
from mmarena.games import make_game
from mmarena.suite import load_suite


def _obs(game, **kw) -> Observation:
    base = dict(
        game=game,
        step=0,
        stage=0,
        revealed=(),
        history=(),
        position=0,
        cash=0.0,
        bid_allowed=True,
        ask_allowed=True,
    )
    base.update(kw)
    return Observation(**base)


@pytest.fixture(scope="module")
def dice():
    for g, _ in load_suite("smoke").episodes_list():
        if g.family == "dice":
            return g
    raise AssertionError("no dice game in smoke suite")


def test_system_has_market_numbers(dice):
    m = dice.market
    system, _ = render_prompt(_obs(dice))
    for needle in (
        f"probability {m.alpha:g}",
        f"standard deviation {m.noise_scale:g}",
        f"multiple of {m.tick:g}",
        f"between -{m.inventory_limit} and +{m.inventory_limit}",
        f"{m.quotes_per_stage} quotes per stage",
        f"{dice.n_steps} quotes in total",
        "knows the settlement value exactly",
        "cash + position x settlement value",
        '{"bid": <number or null>, "ask": <number or null>}',
        "maximise your expected profit",
    ):
        assert needle in system, needle


def test_no_strategy_hints():
    for fam in ("dice", "cards", "transform", "coin", "urn"):
        g = make_game(fam, 3, "perturbed")
        system, user = render_prompt(_obs(g))
        text = (system + user).lower()
        for word in ("bayes", "posterior", "adverse", "selection", "spread", "edge", "conditional"):
            assert word not in text, (fam, word)


def test_reveal_schedule_plain_words(dice):
    _, user = render_prompt(_obs(dice))
    # smoke dice: die 1 before stage 2, die 3 before stage 3, die 2 never.
    assert "Before stage 2: die 1 is revealed." in user
    assert "Before stage 3: die 3 is revealed." in user
    assert "Not revealed before settlement: die 2." in user
    assert dice.contract in user
    assert "Revealed so far: nothing." in user
    assert "History: no quotes yet." in user


def test_static_part_is_identical_across_steps(dice):
    trace = run_episode(dice, _Fixed(), seed=3)
    hist = tuple(
        {k: s[k] for k in ("stage", "bid", "ask", "action", "price")} | {"step": s["t"]}
        for s in trace["steps"][:4]
    )
    a = render_prompt_parts(_obs(dice))
    b = render_prompt_parts(
        _obs(
            dice,
            step=4,
            stage=1,
            history=hist,
            revealed=tuple(trace["revealed"][:1]),
            position=2,
            cash=-20.5,
        )
    )
    assert a[0] == b[0]
    assert a[1][0] == b[1][0]
    assert a[1][1] != b[1][1]


def test_state_rendering(dice):
    hist = (
        {"step": 0, "stage": 0, "bid": 10.0, "ask": 14.0, "action": "buy", "price": 14.0},
        {"step": 1, "stage": 0, "bid": 9.5, "ask": None, "action": "sell", "price": 9.5},
        {"step": 2, "stage": 0, "bid": None, "ask": None, "action": None, "price": None},
    )
    rev = ({"stage": 1, "component": 0, "name": "die 1", "value": 4.0},)
    obs = _obs(
        dice,
        step=3,
        stage=1,
        history=hist,
        revealed=rev,
        position=dice.market.inventory_limit,
        cash=-4.5,
        bid_allowed=False,
    )
    _, user = render_prompt(obs)
    assert f"Stage 2 of {dice.n_stages}, quote 4 of {dice.n_steps}" in user
    assert f"({dice.n_steps - 3} quotes left including this one)" in user
    assert "Revealed so far: die 1 = 4." in user
    assert f"Your position: +{dice.market.inventory_limit} (long). Your cash: -4.5." in user
    assert "ask only" in user
    assert "1 | 1 | 10 | 14 | they bought at your ask (14)" in user
    assert "2 | 1 | 9.5 | - | they sold at your bid (9.5)" in user
    assert "3 | 1 | - | - | none" in user


def test_repair_prompt():
    r = render_repair("STATE", "I think 10 to 12", "no JSON object")
    assert r.startswith("STATE")
    assert "no JSON object" in r and "I think 10 to 12" in r


class _Fixed:
    name = "fixed"

    def reset(self, game):
        pass

    def act(self, obs):
        from mmarena.agents.base import Quote

        g = obs.game
        return Quote(g.prior_mean - 2, g.prior_mean + 2)


@pytest.mark.parametrize(
    "text,expected",
    [
        ('{"bid": 10, "ask": 12}', (10.0, 12.0)),
        ('Reasoning... {"bid": 1, "ask": 2} then\n{"bid": 10.5, "ask": "12.5"}', (10.5, 12.5)),
        ('```json\n{"bid": null, "ask": 7}\n```', (None, 7.0)),
        ('{"bid": "null", "ask": "8"}', (None, 8.0)),
        ('{"note": {"x": 1}, "bid": -3, "ask": 4}', (-3.0, 4.0)),
        ("final: {bid: 9, ask: 11}", (9.0, 11.0)),
        ("{'bid': 9.5, 'ask': None}", (9.5, None)),
        ('{"bid": 12, "ask": 10}', (12.0, 10.0)),  # crossed: the engine flags it
        ('{"mid": 5} and {"bid": 1, "ask": 3} and {"other": 2}', (1.0, 3.0)),
    ],
)
def test_parse_ok(text, expected):
    assert parse_quote(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "I would bid 10 and offer 12.",
        '{"bid": 10}',
        '{"bid": "ten", "ask": 12}',
        '{"bid": true, "ask": 12}',
        '{"bid": NaN, "ask": 12}',
        '{"bid": [1], "ask": 2}',
    ],
)
def test_parse_fail(text):
    with pytest.raises(AgentError):
        parse_quote(text)
