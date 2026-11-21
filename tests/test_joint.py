"""Joint posterior over (hidden informed share, outcome): exactness and the K = 1 reduction."""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from mmarena import joint
from mmarena.engine import _to_tick
from mmarena.games import Game, Market, make_game
from mmarena.market import (
    BUY,
    SELL,
    Posterior,
    optimal_quote,
    quote_value,
    zero_profit_quote,
)

FAMILIES = ("dice", "cards", "transform", "coin", "urn")
ALPHAS = (0.05, 0.5, 0.9)


def _random_path(rng: np.random.Generator, game: Game, posts: list, n: int = 5) -> int:
    """Apply the same random reveals and trades to every posterior in ``posts``."""
    m = game.market
    omega = int(rng.choice(len(game.prob), p=game.prob))
    for t in range(n):
        if t == 2 and game.reveals:
            for c in game.reveals[0]:
                for p in posts:
                    p.reveal(c, float(game.outcomes[omega, c]))
        mu = posts[0].mean()
        sd = max(posts[0].std(), m.tick)
        bid = round(mu - sd * rng.uniform(0.1, 1.5), 1)
        ask = round(mu + sd * rng.uniform(0.1, 1.5), 1)
        action = rng.choice(np.array([BUY, SELL, "none"], dtype=object))
        action = None if action == "none" else str(action)
        for p in posts:
            p.observe_trade(action, bid, ask)
    return omega


@pytest.mark.parametrize("family", FAMILIES)
def test_k1_equals_core_v1_market(family: str) -> None:
    rng = np.random.default_rng(zlib_seed(family))
    for seed in range(4):
        game = make_game(family, 300 + seed)
        m = game.market
        single = joint.Regimes.of([m.alpha])
        v1, v2 = Posterior(game), joint.JointPosterior(game, single)
        _random_path(rng, game, [v1, v2])
        np.testing.assert_allclose(v2.w[0], v1.w, rtol=1e-12, atol=1e-15)
        assert math.isclose(v2.mean(), v1.mean(), rel_tol=1e-12, abs_tol=1e-12)
        assert math.isclose(v2.std(), v1.std(), rel_tol=1e-12, abs_tol=1e-12)
        levels, w, mu = game.levels, v1.level_weights(), v1.mean()
        wl = v2.level_weights()
        np.testing.assert_allclose(wl[0], w, rtol=1e-12, atol=1e-15)
        for _ in range(10):
            bid = round(mu - rng.uniform(-0.5, 2) * game.prior_std, 1)
            ask = round(bid + rng.uniform(0, 3) * game.prior_std, 1)
            for b, a in ((bid, ask), (None, ask), (bid, None)):
                q1 = quote_value(levels, w, mu, b, a, m)
                q2 = joint.quote_value(levels, wl, mu, b, a, single.alpha, m.noise_scale)
                for f in ("p_buy", "p_sell", "capture", "adverse"):
                    assert math.isclose(getattr(q1, f), getattr(q2, f), abs_tol=1e-10), f
        for allow in itertools.product((True, False), repeat=2):
            o1 = optimal_quote(levels, w, mu, m, *allow)
            o2 = joint.optimal_quote(levels, wl, mu, single.alpha, m.noise_scale, m.tick, *allow)
            ev1 = quote_value(levels, w, mu, *o1, m).ev
            ev2 = quote_value(levels, w, mu, *o2, m).ev
            assert math.isclose(ev1, ev2, rel_tol=1e-12, abs_tol=1e-12)
            assert o1 == o2
            z1 = zero_profit_quote(levels, w, mu, m, *allow)
            z2 = joint.zero_profit_quote(
                levels, wl, mu, single.alpha, m.noise_scale, m.tick, *allow
            )
            assert z1 == z2


def zlib_seed(text: str) -> int:
    import zlib

    return zlib.crc32(text.encode())


def _grid_best(levels, wl, mu, alpha, s, tick, allow_bid=True, allow_ask=True) -> float:
    """Brute force: best one-step value over every tick-grid pair (bid <= ask) and no-quote."""
    grid = joint.price_grid(levels, mu, s, tick)
    bids = list(grid) + [None] if allow_bid else [None]
    asks = list(grid) + [None] if allow_ask else [None]
    a_val = {a: joint.quote_value(levels, wl, mu, None, a, alpha, s).ev for a in asks}
    b_val = {b: joint.quote_value(levels, wl, mu, b, None, alpha, s).ev for b in bids}
    best = -math.inf
    for b in bids:
        for a in asks:
            if b is not None and a is not None and b > a:
                continue
            best = max(best, a_val[a] + b_val[b])
    return best


@pytest.mark.parametrize("family", ["dice", "coin", "urn"])
def test_optimum_is_the_grid_argmax_for_public_and_known_alpha(family: str) -> None:
    rng = np.random.default_rng(zlib_seed("grid" + family))
    regimes = joint.Regimes.of(ALPHAS)
    for seed in range(3):
        game = make_game(family, 400 + seed)
        game = _with_market(game, noise_scale=round(0.5 * game.prior_std, 2) or 0.1)
        m = game.market
        post = joint.JointPosterior(game, regimes)
        omega = _random_path(rng, game, [post], n=4)
        post.settle(float(game.value[omega]))
        _random_path(rng, game, [post], n=3)
        levels, wl, mu = game.levels, post.level_weights(), post.mean()
        cases = [(wl, regimes.alpha)] + [post.conditional(k) for k in range(3)]
        for w_case, a_case in cases:
            bid, ask = joint.optimal_quote(levels, w_case, mu, a_case, m.noise_scale, m.tick)
            assert bid is not None and ask is not None and bid <= ask
            got = joint.quote_value(levels, w_case, mu, bid, ask, a_case, m.noise_scale).ev
            best = _grid_best(levels, w_case, mu, a_case, m.noise_scale, m.tick)
            assert got >= best - 1e-12
            for _ in range(50):  # no random quote does better once snapped to the grid
                b = _to_tick(mu + rng.normal(0, 2) * game.prior_std, m.tick, up=False)
                a = _to_tick(b + abs(rng.normal(0, 2)) * game.prior_std, m.tick, up=True)
                v = joint.quote_value(levels, w_case, mu, b, a, a_case, m.noise_scale).ev
                assert v <= got + 1e-9


def _with_market(game: Game, **changes) -> Game:
    from dataclasses import replace

    return replace(game, market=replace(game.market, **changes))


def test_best_pair_never_crosses() -> None:
    bid_v = np.array([0.0, 1.0, 2.0, 5.0, 0.0])
    ask_v = np.array([0.0, 4.0, 1.0, 0.5, 0.0])
    # unconstrained: bid index 3, ask index 1 (crossed); best uncrossed: bid 3 with ask 3
    assert joint.best_pair(bid_v, ask_v) == (3, 3)
    assert joint.best_pair(np.array([3.0, 0.0]), np.array([0.0, 1.0])) == (0, 1)
    assert joint.best_pair(None, ask_v) == (None, 1)
    assert joint.best_pair(bid_v, None) == (3, None)
    rng = np.random.default_rng(3)
    for _ in range(200):
        b, a = rng.normal(size=12), rng.normal(size=12)
        i, j = joint.best_pair(b, a)
        brute = max(b[x] + a[y] for x in range(12) for y in range(x, 12))
        assert i <= j and math.isclose(b[i] + a[j], brute)


def _two_dice() -> Game:
    faces = np.arange(1, 5, dtype=float)
    outcomes = np.array([(a, b) for a in faces for b in faces])
    return Game(
        family="dice",
        variant="perturbed",
        title="two dice",
        description="Two four-sided dice.",
        contract="sum",
        components=("die 1", "die 2"),
        outcomes=outcomes,
        prob=np.full(16, 1 / 16),
        value=outcomes.sum(axis=1),
        reveals=((0,),),
        market=Market(alpha=0.5, noise_scale=1.3, quotes_per_stage=2, tick=0.1),
    )


def test_settlement_update_equals_brute_force_bayes() -> None:
    """Two rounds of a 2-dice game: the regime belief equals enumeration over full histories."""
    game = _two_dice()
    regimes = joint.Regimes(np.array(ALPHAS), np.array([0.2, 0.3, 0.5]))
    s = game.market.noise_scale
    rng = np.random.default_rng(7)
    rounds = []
    post = joint.JointPosterior(game, regimes)
    for _ in range(2):
        omega = int(rng.integers(16))
        steps = []
        for t in range(4):
            if t == 2:
                post.reveal(0, float(game.outcomes[omega, 0]))
            mu = post.mean()
            bid, ask = round(mu - rng.uniform(0.2, 2), 1), round(mu + rng.uniform(0.2, 2), 1)
            action = [BUY, SELL, None][int(rng.integers(3))]
            steps.append((mu, bid, ask, action))
            post.observe_trade(action, bid, ask)
        value = float(game.value[omega])
        rounds.append((omega, steps, value))
        post.settle(value)

    # brute force: P(k | history) ∝ prior_k * prod over rounds of sum over outcomes consistent
    # with the reveal and settlement of prior_i * prod of trade likelihoods
    lik = np.array(regimes.prior, dtype=float)
    for omega, steps, value in rounds:
        die1 = game.outcomes[omega, 0]
        for k, a in enumerate(ALPHAS):
            total = 0.0
            for i in range(16):
                if game.outcomes[i, 0] != die1 or game.value[i] != value:
                    continue
                p = game.prob[i]
                for mu, bid, ask, action in steps:
                    v = game.value[i]
                    pb = a * (v > ask) + (1 - a) * float(_cdf((mu - ask) / s))
                    ps = a * (v < bid) + (1 - a) * float(_cdf((bid - mu) / s))
                    p *= {BUY: pb, SELL: ps, None: 1 - pb - ps}[action]
                total += p
            lik[k] *= total
    np.testing.assert_allclose(post.alpha_w, lik / lik.sum(), rtol=1e-10)


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def test_regimes_validate() -> None:
    with pytest.raises(ValueError):
        joint.Regimes.of([0.1, 0.1])
    with pytest.raises(ValueError):
        joint.Regimes.of([0.1, 1.2])
    r = joint.Regimes.of(ALPHAS, [1, 1, 2])
    assert r.prior.tolist() == [0.25, 0.25, 0.5]
    assert math.isclose(r.mean_alpha, (0.05 + 0.5) / 4 + 0.9 / 2)
    # bit-exact on every machine: it is hashed into the session ids
    assert joint.Regimes.of(ALPHAS).mean_alpha == 0.4833333333333333
