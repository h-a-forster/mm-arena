"""Exact market math: quote values, optimal and zero-profit quotes, taker model, updates."""

from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import tiny_game

from mmarena.games import Market, make_game
from mmarena.market import (
    BUY,
    SELL,
    Posterior,
    optimal_quote,
    quote_value,
    side_values,
    taker_probs,
    zero_profit_quote,
)


def phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def states():
    """A few (levels, weights, mu, market) states, including mid-game posteriors."""
    out = []
    for fam, var, seed in [
        ("dice", "classic", 0),
        ("dice", "perturbed", 4),
        ("cards", "perturbed", 2),
        ("transform", "perturbed", 5),
        ("coin", "perturbed", 1),
        ("urn", "classic", 0),
    ]:
        g = make_game(fam, seed, var)
        post = Posterior(g)
        out.append((g.levels, post.level_weights(), post.mean(), g.market))
        c = g.reveals[0][0]
        post.reveal(c, float(g.outcomes[0, c]))
        mu = post.mean()
        post.observe_trade(BUY, round(mu - 1, 1), round(mu + 1, 1))
        out.append((g.levels, post.level_weights(), post.mean(), g.market))
    lv = np.array([0.0, 3.0, 4.0, 10.0])
    w = np.array([0.1, 0.4, 0.3, 0.2])
    mu = float(w @ lv)
    for ie in (0.0, 0.7, 2.5):
        for alpha in (0.0, 0.3, 0.8):
            out.append(
                (lv, w, mu, Market(alpha=alpha, noise_scale=1.3, informed_noise=ie, tick=0.1))
            )
    return out


STATES = states()


@pytest.mark.parametrize("i", range(len(STATES)))
def test_ev_decomposition_and_adverse_nonnegative(i: int) -> None:
    levels, w, mu, m = STATES[i]
    for bid, ask in [(mu - 1, mu + 1), (mu - 0.05, mu + 3), (None, mu + 0.5), (mu - 2, None)]:
        qv = quote_value(levels, w, mu, bid, ask, m)
        assert qv.ev == pytest.approx(qv.capture - qv.adverse)
        assert qv.adverse >= -1e-12
        # ev directly from the definition
        pb, ps = taker_probs(levels, mu, bid, ask, m)
        direct = 0.0
        if ask is not None:
            direct += float(w @ (pb * (ask - levels)))
        if bid is not None:
            direct += float(w @ (ps * (levels - bid)))
        assert qv.ev == pytest.approx(direct, abs=1e-12)
        assert 0 <= qv.p_buy <= 1 and 0 <= qv.p_sell <= 1
        assert qv.p_buy + qv.p_sell <= 1 + 1e-12


_erf = np.vectorize(math.erf, otypes=[float])


def _ev_grid(levels, w, mu, m, side: str, grid: np.ndarray) -> np.ndarray:
    """One-side expected profit on a price grid, written out from the counterparty model."""
    x = grid[:, None]
    v = levels[None, :]
    s, ie = m.noise_scale, m.informed_noise
    if side == "ask":
        noise = 0.5 * (1 + _erf((mu - x) / s / math.sqrt(2)))
        inf = 0.5 * (1 + _erf((v - x) / ie / math.sqrt(2))) if ie > 0 else (v > x).astype(float)
        profit = x - v
    else:
        noise = 0.5 * (1 + _erf((x - mu) / s / math.sqrt(2)))
        inf = 0.5 * (1 + _erf((x - v) / ie / math.sqrt(2))) if ie > 0 else (v < x).astype(float)
        profit = v - x
    p = m.alpha * inf + (1 - m.alpha) * noise
    return (p * profit) @ w


def _brute(levels, w, mu, m, side: str, step: float, lo: float, hi: float):
    grid = np.arange(math.floor(lo / step), math.ceil(hi / step) + 1) * step
    return grid, _ev_grid(levels, w, mu, m, side, grid)


@pytest.mark.parametrize("i", range(len(STATES)))
def test_optimal_quote_matches_brute_force(i: int) -> None:
    levels, w, mu, m = STATES[i]
    bid, ask = optimal_quote(levels, w, mu, m)
    room = 12 * m.noise_scale + 12 * m.informed_noise + 2
    lo, hi = float(levels[0]) - room, float(levels[-1]) + room
    ev_ask = quote_value(levels, w, mu, None, ask, m).ev
    ev_bid = quote_value(levels, w, mu, bid, None, m).ev
    # same tick grid, much wider range
    for side, ev_opt in (("ask", ev_ask), ("bid", ev_bid)):
        _, ev = _brute(levels, w, mu, m, side, m.tick, lo, hi)
        assert ev_opt == pytest.approx(ev.max(), abs=1e-10), side
        # a continuous-ish grid cannot do much better than the best tick price
        _, fine = _brute(levels, w, mu, m, side, m.tick / 10, lo, hi)
        assert fine.max() >= ev_opt - 1e-12
        assert fine.max() - ev_opt <= m.tick
    # on the tick grid
    assert ask / m.tick == pytest.approx(round(ask / m.tick), abs=1e-6)
    assert bid / m.tick == pytest.approx(round(bid / m.tick), abs=1e-6)
    both = quote_value(levels, w, mu, bid, ask, m)
    assert both.ev == pytest.approx(ev_ask + ev_bid, abs=1e-12)


def test_optimal_quote_respects_allowed_sides() -> None:
    levels, w, mu, m = STATES[0]
    assert optimal_quote(levels, w, mu, m, allow_bid=False)[0] is None
    assert optimal_quote(levels, w, mu, m, allow_ask=False)[1] is None
    assert zero_profit_quote(levels, w, mu, m, allow_bid=False, allow_ask=False) == (None, None)


@pytest.mark.parametrize("i", range(len(STATES)))
def test_zero_profit_quote_is_tightest_nonnegative(i: int) -> None:
    levels, w, mu, m = STATES[i]
    bid, ask = zero_profit_quote(levels, w, mu, m)
    assert quote_value(levels, w, mu, None, ask, m).ev >= -1e-12
    assert quote_value(levels, w, mu, bid, None, m).ev >= -1e-12
    assert quote_value(levels, w, mu, None, ask - m.tick, m).ev < 0
    assert quote_value(levels, w, mu, bid + m.tick, None, m).ev < 0
    ob, oa = optimal_quote(levels, w, mu, m)
    assert ask <= oa + 1e-9 and bid >= ob - 1e-9


def test_glosten_milgrom_conditional_expectation() -> None:
    """With a continuous price, ask = E[V | buy at ask]; on a tick grid it is within a tick."""
    levels, w, mu, m = STATES[0]
    bid, ask = zero_profit_quote(levels, w, mu, m)
    pb, ps = taker_probs(levels, mu, bid, ask, m)
    e_buy = float(w @ (pb * levels)) / float(w @ pb)
    e_sell = float(w @ (ps * levels)) / float(w @ ps)
    assert e_buy - 1e-9 <= ask <= e_buy + m.tick + 1e-9
    assert e_sell - m.tick - 1e-9 <= bid <= e_sell + 1e-9


def test_side_values_matches_quote_value() -> None:
    for levels, w, mu, m in STATES[::3]:
        for side in (BUY, SELL):
            grid, ev = side_values(levels, w, mu, m, side)
            for x, e in list(zip(grid, ev, strict=True))[:: max(1, len(grid) // 15)]:
                q = (
                    quote_value(levels, w, mu, None, float(x), m)
                    if side == BUY
                    else quote_value(levels, w, mu, float(x), None, m)
                )
                assert e == pytest.approx(q.ev, abs=1e-10)


@pytest.mark.parametrize("ie", [0.0, 1.5])
def test_taker_probs_match_simulation(ie: float) -> None:
    m = Market(alpha=0.35, noise_scale=2.0, informed_noise=ie)
    levels = np.array([1.0, 4.0, 5.0, 6.0, 9.0])
    mu, bid, ask = 5.2, 4.5, 6.0
    pb, ps = taker_probs(levels, mu, bid, ask, m)
    rng = np.random.default_rng(1)
    n = 100_000
    for j, v in enumerate(levels):
        informed = rng.random(n) < m.alpha
        val = np.where(
            informed, v + ie * rng.standard_normal(n), mu + m.noise_scale * rng.standard_normal(n)
        )
        buy = val > ask
        sell = ~buy & (val < bid)
        tol = 5 * math.sqrt(0.25 / n)
        assert buy.mean() == pytest.approx(pb[j], abs=tol)
        assert sell.mean() == pytest.approx(ps[j], abs=tol)


def test_taker_probs_one_side() -> None:
    m = Market(alpha=0.5, noise_scale=1.0)
    levels = np.array([0.0, 10.0])
    pb, ps = taker_probs(levels, 5.0, None, 6.0, m)
    assert np.all(ps == 0)
    assert pb == pytest.approx([0.5 * phi(-1.0), 0.5 + 0.5 * phi(-1.0)])
    pb, ps = taker_probs(levels, 5.0, 4.0, None, m)
    assert np.all(pb == 0)
    assert ps == pytest.approx([0.5 + 0.5 * phi(-1.0), 0.5 * phi(-1.0)])


@pytest.mark.parametrize("action", [BUY, SELL, None])
@pytest.mark.parametrize("ie", [0.0, 2.0])
def test_observe_trade_is_bayes_rule(action: str | None, ie: float) -> None:
    m = Market(alpha=0.4, noise_scale=3.0, informed_noise=ie)
    g = tiny_game(market=m)
    prior = [0.2, 0.3, 0.5]
    vals = [0.0, 5.0, 10.0]
    mu = sum(p * v for p, v in zip(prior, vals, strict=True))
    bid, ask = 4.0, 8.0
    lik = []
    for v in vals:
        if ie > 0:
            ib, is_ = phi((v - ask) / ie), phi((bid - v) / ie)
        else:
            ib, is_ = float(v > ask), float(v < bid)
        nb, ns = phi((mu - ask) / 3.0), phi((bid - mu) / 3.0)
        pb, ps = 0.4 * ib + 0.6 * nb, 0.4 * is_ + 0.6 * ns
        lik.append({BUY: pb, SELL: ps, None: 1 - pb - ps}[action])
    post_hand = np.array([p * li for p, li in zip(prior, lik, strict=True)])
    post_hand /= post_hand.sum()
    post = Posterior(g)
    assert post.mean() == pytest.approx(mu)
    post.observe_trade(action, bid, ask)
    assert post.w == pytest.approx(post_hand, abs=1e-12)


def test_posterior_reveal_and_errors() -> None:
    g = make_game("dice", 0, "classic")
    post = Posterior(g)
    post.reveal(0, 6.0)
    assert post.mean() == pytest.approx(13.0)
    assert post.std() ** 2 == pytest.approx(35 / 6)
    cp = post.copy()
    cp.reveal(1, 1.0)
    assert post.mean() == pytest.approx(13.0) and cp.mean() == pytest.approx(10.5)
    with pytest.raises(ValueError):
        cp.reveal(2, 7.0)
    with pytest.raises(ValueError):
        Posterior(g).observe_trade("hold", 1.0, 2.0)
    assert Posterior(g).level_weights().sum() == pytest.approx(1.0)
