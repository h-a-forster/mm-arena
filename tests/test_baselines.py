"""Reference agents: posterior replay, Bayes/Glosten-Milgrom properties, ranking."""

from __future__ import annotations

import numpy as np
import pytest

from mmarena.agents.base import Agent
from mmarena.agents.baselines import (
    BASELINES,
    BayesAgent,
    RandomAgent,
    StaticAgent,
    replay_posterior,
)
from mmarena.engine import run_episode
from mmarena.games import make_game
from mmarena.suite import load_suite

GAMES = [g for g in load_suite("smoke").games()] + [
    make_game(f, 11, "classic") for f in ("dice", "coin", "urn")
]


def test_registry() -> None:
    assert set(BASELINES) == {"bayes", "bayes-noflow", "glosten-milgrom", "static", "random"}
    for name, factory in BASELINES.items():
        agent = factory()
        assert isinstance(agent, Agent)
        assert agent.name == name


class Replayer:
    """Static quotes, but records replay_posterior's mean at each step."""

    name = "replayer"

    def __init__(self, use_flow: bool = True) -> None:
        self.use_flow = use_flow
        self.mus: list[float] = []

    def reset(self, game) -> None:
        self.mus = []
        self.inner = StaticAgent(k=0.3)

    def act(self, obs):
        self.mus.append(replay_posterior(obs, self.use_flow).mean())
        return self.inner.act(obs)


@pytest.mark.parametrize("game", GAMES, ids=lambda g: f"{g.family}-{g.variant}")
def test_replay_posterior_reproduces_engine_mu_exactly(game) -> None:
    for seed in range(3):
        agent = Replayer()
        tr = run_episode(game, agent, seed)
        assert agent.mus == [st["mu"] for st in tr["steps"]]
        tr = run_episode(game, BayesAgent(), seed)
        assert [st["info"]["mu"] for st in tr["steps"]] == [st["mu"] for st in tr["steps"]]


def test_noflow_replay_ignores_trades() -> None:
    g = GAMES[0]
    agent = Replayer(use_flow=False)
    tr = run_episode(g, agent, 0)
    from mmarena.market import Posterior

    for st, mu in zip(tr["steps"], agent.mus, strict=True):
        post = Posterior(g)
        for r in tr["revealed"]:
            if r["stage"] <= st["stage"]:
                post.reveal(r["component"], r["value"])
        assert mu == pytest.approx(post.mean(), abs=1e-12)


@pytest.mark.parametrize("game", GAMES, ids=lambda g: f"{g.family}-{g.variant}")
def test_bayes_agent_plays_the_reference_quote(game) -> None:
    for seed in range(3):
        tr = run_episode(game, BayesAgent(), seed)
        for st in tr["steps"]:
            assert st["invalid"] is None
            # engine rounds quotes to 10 dp; optimal_quote returns raw k * tick floats
            assert st["bid"] == pytest.approx(st["bayes_bid"], abs=1e-9)
            assert st["ask"] == pytest.approx(st["bayes_ask"], abs=1e-9)
            assert st["ev"] == pytest.approx(st["bayes_ev"], abs=1e-12)
            assert st["pulled"] == []
        assert tr["xpnl"] == pytest.approx(tr["bayes_xpnl_local"], abs=1e-9)


def _mean_xpnl(agent_factory, seeds=range(6)) -> float:
    return float(
        np.mean([run_episode(g, agent_factory(), s)["xpnl"] for g in GAMES for s in seeds])
    )


def test_glosten_milgrom_near_zero_nonnegative() -> None:
    gm, bayes = [], []
    for g in GAMES:
        for s in range(6):
            tr = run_episode(g, BayesAgent(zero_profit=True), s)
            assert all(st["ev"] >= -1e-9 for st in tr["steps"])
            gm.append(tr["xpnl"] / max(g.prior_std, 1e-9))
            bayes.append(tr["bayes_xpnl_local"] / max(g.prior_std, 1e-9))
    assert np.mean(gm) >= 0
    assert np.mean(gm) < 0.25 * np.mean(bayes)


def test_bayes_beats_static_and_random() -> None:
    b = _mean_xpnl(BASELINES["bayes"])
    assert b > 0
    assert b > _mean_xpnl(BASELINES["static"])
    assert b > _mean_xpnl(BASELINES["random"])
    assert b >= _mean_xpnl(BASELINES["bayes-noflow"]) - 1e-9


def test_no_agent_beats_reference_stepwise() -> None:
    for g in GAMES:
        for agent in (StaticAgent(), RandomAgent(), BayesAgent(use_flow=False)):
            tr = run_episode(g, agent, 1)
            assert all(st["ev"] <= st["bayes_ev"] + 1e-9 for st in tr["steps"])


def test_static_agent_quotes_prior_band() -> None:
    g = GAMES[0]
    tr = run_episode(g, StaticAgent(k=1.0), 0)
    st = tr["steps"][0]
    tick = g.market.tick
    assert st["bid_quoted"] == pytest.approx(g.prior_mean - g.prior_std)
    assert st["ask_quoted"] == pytest.approx(g.prior_mean + g.prior_std)
    assert abs(st["bid"] - st["bid_quoted"]) <= tick / 2 + 1e-9


def test_random_agent_deterministic_per_game() -> None:
    g = GAMES[1]
    a = run_episode(g, RandomAgent(seed=1), 0)
    b = run_episode(g, RandomAgent(seed=1), 0)
    assert [s["bid_quoted"] for s in a["steps"]] == [s["bid_quoted"] for s in b["steps"]]
