"""Metrics computed from traces."""

from __future__ import annotations

import math

import pytest
from conftest import ScriptedAgent, tiny_game

from mmarena.agents.baselines import BASELINES
from mmarena.engine import run_episode
from mmarena.games import Market, make_game
from mmarena.metrics import (
    aggregate,
    bayes_reference,
    episode_metrics,
    load_episodes,
    select_ok,
)

GAMES = [("dice", 5000), ("coin", 8000), ("urn", 9000), ("cards", 6000)]


def play(agent_name: str, seeds=(0, 1)) -> list[dict]:
    out = []
    for fam, gseed in GAMES:
        game = make_game(fam, gseed, "perturbed")
        for s in seeds:
            out.append(run_episode(game, BASELINES[agent_name](), s))
    return out


@pytest.fixture(scope="module")
def runs() -> dict[str, list[dict]]:
    return {name: play(name) for name in ("bayes", "bayes-noflow", "static", "random")}


def test_select_ok_keeps_last_ok_and_counts_errors():
    g = {"id": "g1"}
    traces = [
        {"game": g, "seed": 0, "status": "error", "tag": 1},
        {"game": g, "seed": 0, "status": "ok", "tag": 2},
        {"game": g, "seed": 0, "status": "ok", "tag": 3},
        {"game": g, "seed": 1, "status": "error", "tag": 4},
        {"game": {"id": "g2"}, "seed": 0, "status": "ok", "tag": 5},
    ]
    ok, n_err = select_ok(traces)
    assert [t["tag"] for t in ok] == [3, 5]
    assert n_err == 1


def test_bayes_scores_itself_at_100(runs):
    ref, made = bayes_reference(runs)
    assert made == 0
    eps = load_episodes(runs)
    agg = aggregate(eps["bayes"].episodes, ref)
    assert agg["edge_captured"] == pytest.approx(100.0)
    assert agg["local_efficiency"] == pytest.approx(1.0)
    assert agg["beta_flow"] == pytest.approx(1.0)
    assert agg["beta_reveal"] == pytest.approx(1.0)
    assert agg["invalid_rate"] == 0 and agg["dominated_rate"] == 0


def test_noflow_and_static_ignore_flow(runs):
    ref, _ = bayes_reference(runs)
    eps = load_episodes(runs)
    noflow = aggregate(eps["bayes-noflow"].episodes, ref)
    static = aggregate(eps["static"].episodes, ref)
    assert noflow["beta_flow"] == pytest.approx(0.0)
    assert noflow["beta_reveal"] > 0.5
    assert static["beta_flow"] == pytest.approx(0.0)
    assert static["beta_reveal"] == pytest.approx(0.0)
    assert static["edge_captured"] < noflow["edge_captured"] < 100


def test_pnl_split_by_taker_adds_up(runs):
    for t in runs["random"]:
        m = episode_metrics(t)
        assert m.pnl_informed_sd + m.pnl_noise_sd == pytest.approx(m.pnl_sd, abs=1e-9)
        assert m.capture_sd - m.adverse_sd == pytest.approx(m.xpnl_sd, abs=1e-9)


def test_reference_generated_on_the_fly(runs):
    without = {k: v for k, v in runs.items() if k != "bayes"}
    ref_gen, made = bayes_reference(without)
    ref, _ = bayes_reference(runs)
    assert made == len(GAMES) * 2
    for k, v in ref.items():
        assert ref_gen[k] == pytest.approx(v)


def test_reference_refuses_unrebuildable_game():
    game = make_game("dice", 5000, "perturbed", market=Market(alpha=0.2, noise_scale=1.0))
    t = run_episode(game, BASELINES["static"](), 0)
    with pytest.raises(ValueError, match="cannot rebuild"):
        bayes_reference({"static": [t]})


def test_hygiene_counts():
    game = tiny_game(market=Market(alpha=0.4, noise_scale=3.0, quotes_per_stage=6))
    script = iter(
        [
            (11.0, 12.0),  # dominated: bid above the highest value
            (4.0, None),  # one-sided by choice
            (None, None),  # no quote
            ValueError("boom"),  # exception
            (6.0, 4.0),  # crossed
            (2.0, 8.0),  # fine
        ]
    )
    t = run_episode(game, ScriptedAgent(lambda obs: next(script)), 0)
    m = episode_metrics(t)
    assert m.dominated == 1
    assert m.one_sided == 1
    assert m.no_quote == 1
    assert m.invalid["exception"] == 1 and m.invalid["crossed"] == 1
    agg = aggregate([m])
    assert agg["invalid_rate"] == pytest.approx(2 / 6)
    assert math.isnan(agg["edge_captured"])  # no reference given
    assert math.isnan(agg["cost_usd"])


def test_inventory_pull_is_not_one_sided():
    game = tiny_game(
        market=Market(alpha=0.0, noise_scale=3.0, quotes_per_stage=8, inventory_limit=1)
    )
    # Bid far above the noise valuation range: noise traders sell until the limit pulls the bid.
    t = run_episode(game, ScriptedAgent(lambda obs: (9.0, 30.0)), 0)
    m = episode_metrics(t)
    assert m.limit_steps > 0
    assert m.one_sided == 0 and m.no_quote == 0


def test_cost_fields_from_info():
    from mmarena.agents.base import Quote

    game = tiny_game()
    agent = ScriptedAgent(
        lambda obs: Quote(
            2.0, 8.0, {"usage": {"input_tokens": 100, "output_tokens": 20}, "cost_usd": 0.01}
        )
    )
    m = episode_metrics(run_episode(game, agent, 0))
    assert m.tokens == 3 * 120
    assert m.cost_usd == pytest.approx(0.03)
    assert m.cost_steps == 3


def test_fill_response_direction():
    game = tiny_game(market=Market(alpha=0.4, noise_scale=3.0, quotes_per_stage=10))

    def follow(obs):
        mid = 5.0
        for h in obs.history:
            mid += 1.0 if h["action"] == "buy" else -1.0 if h["action"] == "sell" else 0.0
        return (mid - 1.0, mid + 1.0)

    def contrarian(obs):
        lo, hi = follow(obs)
        return (10.0 - hi, 10.0 - lo)

    for s in range(5):
        a = episode_metrics(run_episode(game, ScriptedAgent(follow), s))
        b = episode_metrics(run_episode(game, ScriptedAgent(contrarian), s))
        assert a.dir_right == a.dir_n
        assert b.dir_right == 0
