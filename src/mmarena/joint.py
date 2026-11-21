"""Exact market math when the informed share is hidden.

The counterparty model is core-v1's (``market.py``) except that the informed share ``alpha``
is one of ``K`` disclosed values (``Regimes``) with a disclosed prior, fixed for a session and
never revealed. The public posterior is then a weight matrix ``w[k, i]`` over (regime ``k``,
outcome ``i``). Reveals zero out inconsistent outcomes, trades and no-trades reweight by the
core-v1 likelihood with ``alpha`` indexed by ``k``, and a settlement at value ``v`` keeps only
the regime marginal of the outcomes with that value. Every update is exact.

Fill probabilities depend on an outcome only through its settlement value, so pricing works on
joint level weights ``wl[k, l]`` over (regime, distinct value). With ``K = 1`` every function
here equals its counterpart in ``market.py``.

Two expectations matter for scoring (see ``session_engine``): the public one, under ``wl``,
and the regime-conditional one, under row ``k*`` of ``wl`` renormalised with ``alpha[k*]``.
``conditional`` returns the latter's inputs. In both the noise traders centre on the public
mean, which is a function of public information only.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from mmarena.games.base import Game
from mmarena.market import BUY, SELL, QuoteValue, _phi


@dataclass(frozen=True, eq=False)
class Regimes:
    """The disclosed grid of informed shares and its prior."""

    alpha: np.ndarray
    prior: np.ndarray

    def __post_init__(self) -> None:
        alpha = np.asarray(self.alpha, dtype=float).reshape(-1)
        prior = np.asarray(self.prior, dtype=float).reshape(-1)
        if len(alpha) == 0 or alpha.shape != prior.shape:
            raise ValueError("alpha and prior must be non-empty and of equal length")
        if np.any((alpha < 0) | (alpha > 1)):
            raise ValueError(f"every alpha must be in [0, 1], got {alpha.tolist()}")
        if np.any(prior <= 0):
            raise ValueError("every prior weight must be > 0")
        if len(set(alpha.tolist())) != len(alpha):
            raise ValueError("alpha values must be distinct")
        prior = prior / prior.sum()
        for name, arr in (("alpha", alpha), ("prior", prior)):
            arr.setflags(write=False)
            object.__setattr__(self, name, arr)

    @classmethod
    def of(cls, alpha: Sequence[float], prior: Sequence[float] | None = None) -> Regimes:
        prior = [1.0] * len(alpha) if prior is None else prior
        return cls(np.asarray(alpha, dtype=float), np.asarray(prior, dtype=float))

    @property
    def k(self) -> int:
        return len(self.alpha)

    @property
    def mean_alpha(self) -> float:
        return float(self.prior @ self.alpha)

    def to_dict(self) -> dict[str, list[float]]:
        return {"alpha": self.alpha.tolist(), "prior": self.prior.tolist()}


def fill_probs(
    levels: np.ndarray,
    mu: float,
    bid: float | None,
    ask: float | None,
    alpha: np.ndarray,
    noise_scale: float,
) -> tuple[np.ndarray, np.ndarray]:
    """P(counterparty buys at ask | k, V_l) and P(sells at bid | k, V_l), each ``(K, L)``.

    Informed counterparties know the value exactly (``informed_noise`` 0).
    """
    alpha = np.asarray(alpha, dtype=float)
    shape = (len(alpha), len(levels))
    p_buy = np.zeros(shape)
    p_sell = np.zeros(shape)
    if ask is not None:
        noise = float(_phi((mu - ask) / noise_scale))
        p_buy = alpha[:, None] * (levels > ask)[None, :] + ((1 - alpha) * noise)[:, None]
    if bid is not None:
        noise = float(_phi((bid - mu) / noise_scale))
        p_sell = alpha[:, None] * (levels < bid)[None, :] + ((1 - alpha) * noise)[:, None]
    return p_buy, p_sell


def quote_value(
    levels: np.ndarray,
    wl: np.ndarray,
    mu: float,
    bid: float | None,
    ask: float | None,
    alpha: np.ndarray,
    noise_scale: float,
) -> QuoteValue:
    """Exact one-step expectations of a quote under joint level weights ``wl`` (sum 1)."""
    pb, ps = fill_probs(levels, mu, bid, ask, alpha, noise_scale)
    p_buy = float((wl * pb).sum())
    p_sell = float((wl * ps).sum())
    capture = adverse = 0.0
    if ask is not None:
        capture += p_buy * (ask - mu)
        adverse += float((wl * pb * (levels - mu)[None, :]).sum())
    if bid is not None:
        capture += p_sell * (mu - bid)
        adverse += float((wl * ps * (mu - levels)[None, :]).sum())
    return QuoteValue(p_buy, p_sell, capture, adverse)


def price_grid(levels: np.ndarray, mu: float, noise_scale: float, tick: float) -> np.ndarray:
    """Every tick-grid price from below the lowest value to above the highest, both sides.

    The range extends ``5 * noise_scale + tick`` beyond the values (as in ``market.py``), where
    a quote's fill probability is negligible. With the informed share hidden, the value given
    a noise fill is not the public mean, so the optimum is not confined to one side of it.
    """
    room = 5 * noise_scale + tick
    lo = min(float(levels[0]), mu) - room
    hi = max(float(levels[-1]), mu) + room
    return np.round(np.arange(math.floor(lo / tick), math.ceil(hi / tick) + 1) * tick, 10)


def side_values(
    levels: np.ndarray,
    wl: np.ndarray,
    mu: float,
    alpha: np.ndarray,
    noise_scale: float,
    grid: np.ndarray,
    side: str,
) -> np.ndarray:
    """Expected one-step profit of each grid price quoted alone on one side."""
    alpha = np.asarray(alpha, dtype=float)
    informed_w = alpha @ wl  # (L,) mass of informed fills per value
    noise_w = 1.0 - alpha
    m0 = float(noise_w @ wl.sum(axis=1))
    m1 = float(noise_w @ (wl @ levels))
    if side == BUY:
        inf = ((levels[None, :] > grid[:, None]) * (grid[:, None] - levels[None, :])) @ informed_w
        return inf + _phi((mu - grid) / noise_scale) * (grid * m0 - m1)
    if side == SELL:
        inf = ((levels[None, :] < grid[:, None]) * (levels[None, :] - grid[:, None])) @ informed_w
        return inf + _phi((grid - mu) / noise_scale) * (m1 - grid * m0)
    raise ValueError(f"unknown side {side!r}")


def optimal_quote(
    levels: np.ndarray,
    wl: np.ndarray,
    mu: float,
    alpha: np.ndarray,
    noise_scale: float,
    tick: float,
    allow_bid: bool = True,
    allow_ask: bool = True,
) -> tuple[float | None, float | None]:
    """Myopic optimum: the tick-grid pair with bid <= ask that maximises one-step profit.

    Buys and sells are disjoint events for an uncrossed quote, so profit is the sum of the two
    sides' values. Each side is searched over the whole grid: with the informed share hidden
    (or known while the noise traders centre on the public mean) the optimum can lie on the
    far side of the public mean. A side's value is positive only on its own side of the value
    expected given a noise fill, so the two optima do not cross; ``best_pair`` enforces
    bid <= ask regardless. Ties go to the lowest ask and the highest bid (the tightest market),
    as in ``market.optimal_quote``.
    """
    grid = price_grid(levels, mu, noise_scale, tick)
    ask_v = side_values(levels, wl, mu, alpha, noise_scale, grid, BUY) if allow_ask else None
    bid_v = side_values(levels, wl, mu, alpha, noise_scale, grid, SELL) if allow_bid else None
    ib, ia = best_pair(bid_v, ask_v)
    bid = float(grid[ib]) if ib is not None else None
    ask = float(grid[ia]) if ia is not None else None
    return bid, ask


def best_pair(bid_v: np.ndarray | None, ask_v: np.ndarray | None) -> tuple[int | None, int | None]:
    """Indices maximising ``bid_v[i] + ask_v[j]`` with ``i <= j`` (same price grid).

    Ties go to the lowest ask and then the highest bid. A missing side is ``None``.
    """
    ia = int(np.argmax(ask_v)) if ask_v is not None else None
    ib = len(bid_v) - 1 - int(np.argmax(bid_v[::-1])) if bid_v is not None else None
    if ia is None or ib is None or ib <= ia:
        return ib, ia
    best_b = np.empty(len(bid_v), dtype=int)  # highest-valued bid at or below each index
    cur = 0
    for j in range(len(bid_v)):
        if bid_v[j] >= bid_v[cur]:
            cur = j
        best_b[j] = cur
    ia = int(np.argmax(ask_v + bid_v[best_b]))
    return int(best_b[ia]), ia


def zero_profit_quote(
    levels: np.ndarray,
    wl: np.ndarray,
    mu: float,
    alpha: np.ndarray,
    noise_scale: float,
    tick: float,
    allow_bid: bool = True,
    allow_ask: bool = True,
) -> tuple[float | None, float | None]:
    """Glosten-Milgrom quote: the tightest prices with non-negative expected profit.

    Asks are searched at or above the public mean and bids at or below it, as in
    ``market.zero_profit_quote``.
    """
    grid = price_grid(levels, mu, noise_scale, tick)
    bid = ask = None
    if allow_ask:
        g = grid[grid >= math.floor(mu / tick) * tick - 1e-9]
        ev = side_values(levels, wl, mu, alpha, noise_scale, g, BUY)
        ok = np.flatnonzero(ev >= -1e-12)
        ask = float(g[ok[0]]) if len(ok) else float(g[-1])
    if allow_bid:
        g = grid[grid <= math.ceil(mu / tick) * tick + 1e-9]
        ev = side_values(levels, wl, mu, alpha, noise_scale, g, SELL)
        ok = np.flatnonzero(ev >= -1e-12)
        bid = float(g[ok[-1]]) if len(ok) else float(g[0])
    return bid, ask


class JointPosterior:
    """Exact public posterior over (regime, outcome) for one session.

    ``alpha_w`` is the regime belief carried from round to round; ``w`` is the joint belief
    within the current round.
    """

    def __init__(self, game: Game, regimes: Regimes) -> None:
        if game.market.informed_noise != 0:
            raise ValueError("hidden-alpha sessions need informed_noise = 0")
        self.game = game
        self.regimes = regimes
        self.alpha = regimes.alpha
        self.noise_scale = game.market.noise_scale
        self.alpha_w = regimes.prior.astype(float).copy()
        self.w = np.empty((regimes.k, len(game.prob)))
        self.start_round()

    def copy(self) -> JointPosterior:
        other = type(self).__new__(type(self))
        other.__dict__.update(self.__dict__)
        other.alpha_w = self.alpha_w.copy()
        other.w = self.w.copy()
        return other

    def start_round(self) -> None:
        self.w = self.alpha_w[:, None] * self.game.prob[None, :]

    def _normalise(self, what: str) -> None:
        total = self.w.sum()
        if not total > 0:
            raise ValueError(f"posterior collapsed to zero after {what}")
        self.w /= total

    def reveal(self, component: int, value: float) -> None:
        self.w = self.w * (self.game.outcomes[:, component] == value)[None, :]
        self._normalise(f"revealing component {component} = {value}")

    def observe_trade(self, action: str | None, bid: float | None, ask: float | None) -> None:
        pb, ps = fill_probs(self.game.levels, self.mean(), bid, ask, self.alpha, self.noise_scale)
        if action == BUY:
            lik = pb
        elif action == SELL:
            lik = ps
        elif action is None:
            lik = 1.0 - pb - ps
        else:
            raise ValueError(f"unknown action {action!r}")
        self.w = self.w * np.clip(lik, 0.0, 1.0)[:, self.game.level_index]
        self._normalise(f"observing {action or 'no trade'}")

    def settle(self, value: float) -> None:
        """End of round: the settlement value is public; carry the regime belief forward."""
        mass = self.w[:, self.game.value == value].sum(axis=1)
        if not mass.sum() > 0:
            raise ValueError(f"settlement value {value} has zero posterior mass")
        self.alpha_w = mass / mass.sum()
        self.start_round()

    def regime_weights(self) -> np.ndarray:
        return self.w.sum(axis=1)

    def level_weights(self) -> np.ndarray:
        """Joint weights over (regime, distinct value), shape ``(K, L)``."""
        g = self.game
        return np.stack(
            [np.bincount(g.level_index, weights=row, minlength=len(g.levels)) for row in self.w]
        )

    def mean(self) -> float:
        return float(self.w.sum(axis=0) @ self.game.value)

    def std(self) -> float:
        mu = self.mean()
        return float(np.sqrt(max(self.w.sum(axis=0) @ (self.game.value - mu) ** 2, 0.0)))

    def conditional(self, k: int) -> tuple[np.ndarray, np.ndarray]:
        """``(wl, alpha)`` given regime ``k``: row ``k`` of the level weights, renormalised."""
        row = self.level_weights()[k : k + 1]
        total = row.sum()
        if not total > 0:
            raise ValueError(f"regime {k} has zero posterior mass")
        return row / total, self.alpha[k : k + 1]
