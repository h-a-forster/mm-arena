"""Exact Bayesian market math.

The public posterior is a weight vector over the game's enumerated outcomes. Reveals zero out
inconsistent outcomes; trades and no-trades reweight by the counterparty model's likelihood.
Fill probabilities depend on an outcome only through its settlement value, so pricing works on
the compressed distribution over distinct values (``levels``).

Conventions: ``"buy"`` means the counterparty buys at the market maker's ask (the market maker
sells one unit); ``"sell"`` means the counterparty sells at the bid (the market maker buys).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from mmarena.games.base import Game, Market

BUY, SELL = "buy", "sell"


def _phi(x: np.ndarray | float) -> np.ndarray:
    """Standard normal CDF."""
    x = np.asarray(x, dtype=float)
    return 0.5 * (1.0 + _erf(x / math.sqrt(2.0)))


_erf = np.vectorize(math.erf, otypes=[float])


def taker_probs(
    levels: np.ndarray, mu: float, bid: float | None, ask: float | None, market: Market
) -> tuple[np.ndarray, np.ndarray]:
    """P(counterparty buys at ask | V) and P(counterparty sells at bid | V), per value level."""
    a = market.alpha
    p_buy = np.zeros(len(levels))
    p_sell = np.zeros(len(levels))
    if ask is not None:
        noise = float(_phi((mu - ask) / market.noise_scale))
        if market.informed_noise > 0:
            inf = _phi((levels - ask) / market.informed_noise)
        else:
            inf = (levels > ask).astype(float)
        p_buy = a * inf + (1 - a) * noise
    if bid is not None:
        noise = float(_phi((bid - mu) / market.noise_scale))
        if market.informed_noise > 0:
            inf = _phi((bid - levels) / market.informed_noise)
        else:
            inf = (levels < bid).astype(float)
        p_sell = a * inf + (1 - a) * noise
    return p_buy, p_sell


@dataclass(frozen=True)
class QuoteValue:
    """Exact one-step expectations for a quote under the current posterior.

    ``ev = capture - adverse``. ``capture`` is the spread earned against the pre-trade fair
    value; ``adverse`` is the expected value of the information the counterparty trades on.
    """

    p_buy: float
    p_sell: float
    capture: float
    adverse: float

    @property
    def ev(self) -> float:
        return self.capture - self.adverse


def quote_value(
    levels: np.ndarray,
    w: np.ndarray,
    mu: float,
    bid: float | None,
    ask: float | None,
    market: Market,
) -> QuoteValue:
    pb, ps = taker_probs(levels, mu, bid, ask, market)
    p_buy = float(w @ pb)
    p_sell = float(w @ ps)
    capture = 0.0
    adverse = 0.0
    if ask is not None:
        capture += p_buy * (ask - mu)
        adverse += float(w @ (pb * (levels - mu)))
    if bid is not None:
        capture += p_sell * (mu - bid)
        adverse += float(w @ (ps * (mu - levels)))
    return QuoteValue(p_buy, p_sell, capture, adverse)


def _side_grid(mu: float, lo: float, hi: float, tick: float) -> np.ndarray:
    start = math.floor(lo / tick)
    stop = math.ceil(hi / tick)
    return np.arange(start, stop + 1) * tick


def side_values(
    levels: np.ndarray, w: np.ndarray, mu: float, market: Market, side: str
) -> tuple[np.ndarray, np.ndarray]:
    """Expected one-step profit of every tick-grid price on one side (vectorised)."""
    spread_room = 5 * market.noise_scale + 5 * market.informed_noise + market.tick
    if side == BUY:  # ask side
        grid = _side_grid(mu, mu, max(levels[-1], mu) + spread_room, market.tick)
        noise = _phi((mu - grid) / market.noise_scale)
        if market.informed_noise > 0:
            inf = _phi((levels[None, :] - grid[:, None]) / market.informed_noise)
        else:
            inf = (levels[None, :] > grid[:, None]).astype(float)
        p = market.alpha * inf + (1 - market.alpha) * noise[:, None]
        ev = (p * (grid[:, None] - levels[None, :])) @ w
    else:  # bid side
        grid = _side_grid(mu, min(levels[0], mu) - spread_room, mu, market.tick)
        noise = _phi((grid - mu) / market.noise_scale)
        if market.informed_noise > 0:
            inf = _phi((grid[:, None] - levels[None, :]) / market.informed_noise)
        else:
            inf = (levels[None, :] < grid[:, None]).astype(float)
        p = market.alpha * inf + (1 - market.alpha) * noise[:, None]
        ev = (p * (levels[None, :] - grid[:, None])) @ w
    return grid, ev


def optimal_quote(
    levels: np.ndarray,
    w: np.ndarray,
    mu: float,
    market: Market,
    allow_bid: bool = True,
    allow_ask: bool = True,
) -> tuple[float | None, float | None]:
    """Myopic Bayes-optimal quote: each side maximises one-step expected profit on the tick grid."""
    bid = ask = None
    if allow_ask:
        grid, ev = side_values(levels, w, mu, market, BUY)
        ask = float(grid[int(np.argmax(ev))])
    if allow_bid:
        grid, ev = side_values(levels, w, mu, market, SELL)
        # argmax over a reversed grid picks the highest bid among ties (tightest market)
        i = len(grid) - 1 - int(np.argmax(ev[::-1]))
        bid = float(grid[i])
    return bid, ask


def zero_profit_quote(
    levels: np.ndarray,
    w: np.ndarray,
    mu: float,
    market: Market,
    allow_bid: bool = True,
    allow_ask: bool = True,
) -> tuple[float | None, float | None]:
    """Glosten-Milgrom quote: the tightest tick-grid prices with non-negative expected profit.

    In a competitive dealer market this is ``ask = E[V | buy at ask]`` and
    ``bid = E[V | sell at bid]``: the spread exactly covers adverse selection.
    """
    bid = ask = None
    if allow_ask:
        grid, ev = side_values(levels, w, mu, market, BUY)
        ok = np.flatnonzero(ev >= -1e-12)
        ask = float(grid[ok[0]]) if len(ok) else float(grid[-1])
    if allow_bid:
        grid, ev = side_values(levels, w, mu, market, SELL)
        ok = np.flatnonzero(ev >= -1e-12)
        bid = float(grid[ok[-1]]) if len(ok) else float(grid[0])
    return bid, ask


class Posterior:
    """Exact public posterior over a game's outcomes."""

    def __init__(self, game: Game) -> None:
        self.game = game
        self.w = np.array(game.prob, dtype=float)

    def copy(self) -> Posterior:
        other = Posterior.__new__(Posterior)
        other.game = self.game
        other.w = self.w.copy()
        return other

    def _normalise(self, what: str) -> None:
        total = self.w.sum()
        if not total > 0:
            raise ValueError(f"posterior collapsed to zero after {what}")
        self.w /= total

    def reveal(self, component: int, value: float) -> None:
        self.w = self.w * (self.game.outcomes[:, component] == value)
        self._normalise(f"revealing component {component} = {value}")

    def level_weights(self) -> np.ndarray:
        return np.bincount(self.game.level_index, weights=self.w, minlength=len(self.game.levels))

    def mean(self) -> float:
        return float(self.w @ self.game.value)

    def std(self) -> float:
        mu = self.mean()
        return float(np.sqrt(max(self.w @ (self.game.value - mu) ** 2, 0.0)))

    def observe_trade(self, action: str | None, bid: float | None, ask: float | None) -> None:
        """Update on the step's outcome: a buy at the ask, a sell at the bid, or no trade."""
        levels = self.game.levels
        pb, ps = taker_probs(levels, self.mean(), bid, ask, self.game.market)
        if action == BUY:
            lik = pb
        elif action == SELL:
            lik = ps
        elif action is None:
            lik = 1.0 - pb - ps
        else:
            raise ValueError(f"unknown action {action!r}")
        self.w = self.w * np.clip(lik, 0.0, 1.0)[self.game.level_index]
        self._normalise(f"observing {action or 'no trade'}")
