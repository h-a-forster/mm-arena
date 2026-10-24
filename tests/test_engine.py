"""Episode simulator: posterior and scoring statistics, CRN, validation paths."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
from conftest import ScriptedAgent, tiny_game

from mmarena.agents.base import AgentError, InfraError, Quote
from mmarena.agents.baselines import BayesAgent, RandomAgent, StaticAgent
from mmarena.engine import TRACE_VERSION, draw_episode, run_episode
from mmarena.games import Market, make_game
from mmarena.market import Posterior

N_CAL = 1500


def _z(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    sd = x.std(ddof=1)
    return float(x.mean() / (sd / math.sqrt(len(x)))) if sd > 0 else 0.0


CAL_GAMES = {
    "coin-exact-informed": make_game(
        "coin",
        0,
        "classic",
        market=Market(alpha=0.35, noise_scale=1.5, quotes_per_stage=2, inventory_limit=3),
    ),
    "urn-noisy-informed": make_game(
        "urn",
        2,
        "perturbed",
        market=Market(alpha=0.5, noise_scale=2.0, informed_noise=1.0, quotes_per_stage=1, tick=0.5),
    ),
}


@pytest.fixture(scope="module", params=sorted(CAL_GAMES))
def batch(request):
    """Many episodes of one game with a fixed public-information policy (static, tight)."""
    g = CAL_GAMES[request.param]
    agent = StaticAgent(k=0.4)
    traces = [run_episode(g, agent, s) for s in range(N_CAL)]
    assert all(t["status"] == "ok" for t in traces)
    return g, traces


def test_posterior_mean_unbiased_each_step(batch) -> None:
    g, traces = batch
    for t in range(g.n_steps):
        d = np.array([tr["value"] - tr["steps"][t]["mu"] for tr in traces])
        assert abs(_z(d)) < 4.5, (t, d.mean())
        d_after = np.array([tr["value"] - tr["steps"][t]["mu_after"] for tr in traces])
        assert abs(_z(d_after)) < 4.5, (t, d_after.mean())


def test_fill_probabilities_calibrated(batch) -> None:
    g, traces = batch
    for key, act in (("p_buy", "buy"), ("p_sell", "sell")):
        for t in range(g.n_steps):
            p = np.array([tr["steps"][t][key] for tr in traces])
            hit = np.array([tr["steps"][t]["action"] == act for tr in traces], dtype=float)
            var = float((p * (1 - p)).sum())
            if var < 1e-6:
                assert hit.sum() == pytest.approx(p.sum(), abs=1e-6)
                continue
            z = (hit.sum() - p.sum()) / math.sqrt(var)
            assert abs(z) < 4.5, (key, t, hit.mean(), p.mean())


def test_taker_type_frequency(batch) -> None:
    g, traces = batch
    informed = np.array([s["taker"] == "informed" for tr in traces for s in tr["steps"]], float)
    a = g.market.alpha
    z = (informed.sum() - a * len(informed)) / math.sqrt(a * (1 - a) * len(informed))
    assert abs(z) < 4.5


def test_xpnl_unbiased_for_pnl(batch) -> None:
    _, traces = batch
    d = np.array([tr["pnl"] - tr["xpnl"] for tr in traces])
    assert abs(_z(d)) < 4.0, d.mean()
    # and xpnl really is the lower-variance estimator
    assert np.var([tr["xpnl"] for tr in traces]) < np.var([tr["pnl"] for tr in traces])


def test_hidden_outcome_frequency_matches_prior() -> None:
    g = CAL_GAMES["coin-exact-informed"]
    vals = np.array([g.value[draw_episode(g, s)["omega"]] for s in range(4000)])
    assert abs((vals.mean() - g.prior_mean) / (g.prior_std / math.sqrt(len(vals)))) < 4.5


@pytest.mark.slow
def test_xpnl_unbiased_bayes_agent_large() -> None:
    g = CAL_GAMES["coin-exact-informed"]
    traces = [run_episode(g, BayesAgent(), s) for s in range(3000)]
    d = np.array([tr["pnl"] - tr["xpnl"] for tr in traces])
    assert abs(_z(d)) < 4.0
    for t in range(g.n_steps):
        assert abs(_z(np.array([tr["value"] - tr["steps"][t]["mu"] for tr in traces]))) < 4.5


# --------------------------------------------------------------------------- trace bookkeeping


def test_trace_consistency_and_json(coin_game) -> None:
    for seed in range(10):
        tr = run_episode(coin_game, StaticAgent(k=0.3), seed)
        s = json.dumps(tr, allow_nan=False)
        assert json.loads(s) == tr
        assert tr["trace_version"] == TRACE_VERSION and tr["status"] == "ok"
        assert set(tr["provenance"]) == {"mmarena"}  # baselines add nothing of their own
        assert len(tr["steps"]) == coin_game.n_steps
        pos, cash = 0, 0.0
        for st in tr["steps"]:
            if st["action"] == "buy":
                pos, cash = pos - 1, cash + st["ask"]
                assert st["price"] == st["ask"]
            elif st["action"] == "sell":
                pos, cash = pos + 1, cash - st["bid"]
                assert st["price"] == st["bid"]
            else:
                assert st["price"] is None
            assert st["position"] == pos and st["cash"] == pytest.approx(cash)
            assert st["lo"] <= st["mu"] <= st["hi"]
            assert st["ev"] == pytest.approx(st["capture"] - st["adverse"])
            assert st["ev"] <= st["bayes_ev"] + 1e-9
        assert tr["position"] == pos
        assert tr["pnl"] == pytest.approx(cash + pos * tr["value"])
        assert tr["xpnl"] == pytest.approx(sum(st["ev"] for st in tr["steps"]))
        # reveals are true hidden values, at the right stages
        hidden = tr["hidden"]
        for r in tr["revealed"]:
            assert hidden[r["name"]] == r["value"]
            assert r["component"] in coin_game.reveals[r["stage"] - 1]
        assert len(tr["revealed"]) == sum(len(gr) for gr in coin_game.reveals)
        # mu_after at t equals mu at t+1 within a stage
        for a, b in zip(tr["steps"], tr["steps"][1:], strict=False):
            if a["stage"] == b["stage"]:
                assert a["mu_after"] == b["mu"]


def test_engine_mu_matches_independent_posterior(coin_game) -> None:
    tr = run_episode(coin_game, StaticAgent(k=0.2), 3)
    post = Posterior(coin_game)
    revealed = {r["stage"]: [] for r in tr["revealed"]}
    for r in tr["revealed"]:
        revealed[r["stage"]].append(r)
    stage = 0
    for st in tr["steps"]:
        if st["stage"] != stage:
            stage = st["stage"]
            for r in revealed.get(stage, []):
                post.reveal(r["component"], r["value"])
        assert post.mean() == pytest.approx(st["mu"], abs=1e-12)
        post.observe_trade(st["action"], st["bid"], st["ask"])
        assert post.mean() == pytest.approx(st["mu_after"], abs=1e-12)


def test_common_random_numbers(coin_game) -> None:
    for seed in range(8):
        a = run_episode(coin_game, StaticAgent(k=0.5), seed)
        b = run_episode(coin_game, RandomAgent(seed=3), seed)
        c = run_episode(coin_game, BayesAgent(), seed)
        assert a["hidden"] == b["hidden"] == c["hidden"]
        assert a["value"] == b["value"] == c["value"]
        assert a["revealed"] == b["revealed"] == c["revealed"]
        ta = [s["taker"] for s in a["steps"]]
        assert ta == [s["taker"] for s in b["steps"]] == [s["taker"] for s in c["steps"]]
    # different episode seeds give different draws
    hs = {json.dumps(run_episode(coin_game, StaticAgent(), s)["hidden"]) for s in range(20)}
    assert len(hs) > 5


def test_draws_depend_only_on_game_and_seed(coin_game) -> None:
    d1, d2 = draw_episode(coin_game, 5), draw_episode(coin_game, 5)
    assert d1["omega"] == d2["omega"]
    for k in ("u", "z", "e"):
        assert np.array_equal(d1[k], d2[k])


def test_noise_trader_valuation_uses_draws() -> None:
    """Reproduce each step's fill from the pre-drawn shocks and the logged state."""
    g = make_game(
        "urn", 1, "classic", market=Market(alpha=0.4, noise_scale=1.0, informed_noise=0.5)
    )
    for seed in range(5):
        tr = run_episode(g, StaticAgent(k=0.3), seed)
        d = draw_episode(g, seed)
        for t, st in enumerate(tr["steps"]):
            informed = d["u"][t] < g.market.alpha
            assert st["taker"] == ("informed" if informed else "noise")
            val = (
                tr["value"] + g.market.informed_noise * d["e"][t]
                if informed
                else st["mu"] + g.market.noise_scale * d["z"][t]
            )
            exp = (
                "buy"
                if st["ask"] is not None and val > st["ask"]
                else ("sell" if st["bid"] is not None and val < st["bid"] else None)
            )
            assert st["action"] == exp


# --------------------------------------------------------------------------- validation paths


def _game(**kw):
    market = Market(
        **{"alpha": 0.3, "noise_scale": 1.0, "quotes_per_stage": 4, "inventory_limit": 2, **kw}
    )
    return make_game("coin", 0, "classic", market=market)


def test_crossed_quote_invalid_no_trade() -> None:
    g = _game()
    tr = run_episode(g, ScriptedAgent(lambda o: (5.0, 4.0)), 0)
    for st in tr["steps"]:
        assert st["invalid"] == "crossed"
        assert st["bid"] is None and st["ask"] is None and st["action"] is None
        assert st["bid_quoted"] == 5.0 and st["ask_quoted"] == 4.0
        assert st["ev"] == 0.0 and st["p_buy"] == 0.0 and st["p_sell"] == 0.0
    assert tr["pnl"] == 0.0 and tr["xpnl"] == 0.0


@pytest.mark.parametrize(
    "quote, kind",
    [
        ((math.nan, 5.0), "nonfinite"),
        ((1.0, math.inf), "nonfinite"),
        (("abc", 5.0), "nonfinite"),
        (AgentError("bad format"), "format"),
        (ValueError("boom"), "exception"),
        (Quote(None, None), None),
    ],
)
def test_invalid_quote_kinds(quote, kind) -> None:
    g = _game()
    tr = run_episode(g, ScriptedAgent(lambda o: quote), 0)
    assert tr["status"] == "ok"
    for st in tr["steps"]:
        assert st["invalid"] == kind
        assert st["bid"] is None and st["ask"] is None and st["action"] is None
    assert json.dumps(tr, allow_nan=False)
    if kind == "format":
        assert tr["steps"][0]["info"]["error"] == "bad format"
    if kind == "exception":
        assert tr["steps"][0]["info"]["error"] == "ValueError: boom"


def test_non_quote_return_is_exception() -> None:
    g = _game()
    agent = ScriptedAgent(lambda o: None)
    agent.act = lambda obs: "bid 3 ask 4"  # type: ignore[method-assign]
    tr = run_episode(g, agent, 0)
    assert all(st["invalid"] == "exception" for st in tr["steps"])


def test_infra_error_aborts_episode() -> None:
    g = _game()
    agent = ScriptedAgent(lambda o: InfraError("rate limited") if o.step == 2 else (2.0, 4.0))
    tr = run_episode(g, agent, 0)
    assert tr["status"] == "error"
    assert "rate limited" in tr["error"]
    assert tr["pnl"] is None and tr["xpnl"] is None and tr["bayes_xpnl_local"] is None
    assert len(tr["steps"]) == 2
    json.dumps(tr, allow_nan=False)


def test_tick_rounding_widens() -> None:
    g = _game(tick=0.5)
    tr = run_episode(g, ScriptedAgent(lambda o: (2.26, 3.74)), 0)
    st = tr["steps"][0]
    assert (st["bid"], st["ask"]) == (2.0, 4.0)
    assert (st["bid_quoted"], st["ask_quoted"]) == (2.26, 3.74)
    # on-grid quotes are untouched despite float noise (9.5 / 0.1 != 95 exactly)
    g = _game(tick=0.1)
    tr = run_episode(g, ScriptedAgent(lambda o: (9.5, 9.7)), 0)
    assert (tr["steps"][0]["bid"], tr["steps"][0]["ask"]) == (9.5, 9.7)
    tr = run_episode(g, ScriptedAgent(lambda o: (3.14159, 3.86)), 0)
    assert (tr["steps"][0]["bid"], tr["steps"][0]["ask"]) == (3.1, 3.9)
    # widening never crosses a valid quote; a locked quote stays valid
    tr = run_episode(g, ScriptedAgent(lambda o: (3.5, 3.5)), 0)
    assert tr["steps"][0]["bid"] == tr["steps"][0]["ask"] == 3.5
    assert tr["steps"][0]["invalid"] is None


@pytest.mark.parametrize("side", ["bid", "ask"])
def test_inventory_limit_pulls_right_side(side: str) -> None:
    g = _game()  # limit 2, 12 steps
    lim = g.market.inventory_limit
    # quote a side every counterparty will hit
    quote = (1000.0, None) if side == "bid" else (None, -1000.0)
    tr = run_episode(g, ScriptedAgent(lambda o: quote), 0)
    pos_before = 0
    for st in tr["steps"]:
        at_limit = pos_before == (lim if side == "bid" else -lim)
        assert st["bid_allowed"] == (pos_before < lim)
        assert st["ask_allowed"] == (pos_before > -lim)
        if at_limit:
            assert st["pulled"] == [side]
            assert st[side] is None and st["action"] is None
            assert st["bayes_" + side] is None
        else:
            assert st["pulled"] == []
            assert st["action"] == ("sell" if side == "bid" else "buy")
        pos_before = st["position"]
    assert abs(tr["position"]) == lim


def test_inventory_pull_keeps_other_side() -> None:
    g = _game()
    # long the limit quickly, then quote both sides; only the bid is pulled
    tr = run_episode(
        g, ScriptedAgent(lambda o: (1000.0, None) if o.position < 2 else (1.0, 9.0)), 0
    )
    late = [st for st in tr["steps"] if not st["bid_allowed"]]
    assert late
    for st in late:
        assert st["pulled"] == ["bid"] and st["bid"] is None and st["ask"] == 9.0


def test_observation_contents(coin_game) -> None:
    agent = ScriptedAgent(lambda o: (1.0, 6.0))
    tr = run_episode(coin_game, agent, 4)
    assert len(agent.seen) == coin_game.n_steps
    for t, obs in enumerate(agent.seen):
        assert obs.step == t and obs.stage == coin_game.stage_of(t)
        assert len(obs.history) == t
        assert obs.steps_left == coin_game.n_steps - t
        assert all(r["stage"] <= obs.stage for r in obs.revealed)
        # no hidden information leaks beyond reveals
        assert len(obs.revealed) == sum(len(gr) for gr in coin_game.reveals[: obs.stage])
    assert tr["status"] == "ok"


# --------------------------------------------------------------------------- tiny-game exactness


def test_tiny_game_single_step_ev_exact() -> None:
    m = Market(alpha=0.4, noise_scale=3.0, quotes_per_stage=1)
    g = tiny_game(market=m)
    tr = run_episode(g, ScriptedAgent(lambda o: (4.0, 8.0)), 0)
    st = tr["steps"][0]
    phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))  # noqa: E731
    mu = 0.3 * 5 + 0.5 * 10
    pb = {v: 0.4 * (v > 8) + 0.6 * phi((mu - 8) / 3) for v in (0, 5, 10)}
    ps = {v: 0.4 * (v < 4) + 0.6 * phi((4 - mu) / 3) for v in (0, 5, 10)}
    w = {0: 0.2, 5: 0.3, 10: 0.5}
    ev = sum(w[v] * (pb[v] * (8 - v) + ps[v] * (v - 4)) for v in w)
    assert st["mu"] == pytest.approx(mu)
    assert st["ev"] == pytest.approx(ev, abs=1e-12)
    assert st["p_buy"] == pytest.approx(sum(w[v] * pb[v] for v in w))
