"""Reference market makers with white-box access to the game.

- ``bayes``: exact public posterior, myopic profit-maximising quote. The reference score.
- ``bayes-noflow``: same, but its belief ignores order flow (updates on reveals only). The gap
  to ``bayes`` is the value of learning from fills.
- ``bayes-mean``: quotes the exact posterior mean +/- ``MEAN_K`` posterior sds. Isolates the value
  of a correct belief from the value of a profit-maximising quote.
- ``bayes-lookahead``: one-step lookahead. Maximises immediate expected profit plus the expected
  myopic-optimal profit at the next step, so it prices in the information its own quote
  generates. The gap to ``bayes`` bounds how much a non-myopic policy could add.
- ``glosten-milgrom``: exact posterior, zero-profit (competitive) quote. Expected P&L ~ 0; a
  check on the simulator and a reminder that a tight market is not a profitable one.
- ``static``: prior mean +/- one prior standard deviation, never updated.
- ``random``: random mid and width around the prior. A floor.
"""

from __future__ import annotations

import numpy as np

from mmarena.agents.base import Observation, Quote
from mmarena.games.base import Game
from mmarena.market import (
    Posterior,
    optimal_quote,
    quote_value,
    taker_probs,
    zero_profit_quote,
)


def replay_posterior(obs: Observation, use_flow: bool = True) -> Posterior:
    """Rebuild the public posterior from an observation's reveals and trade history."""
    game = obs.game
    post = Posterior(game)
    by_stage: dict[int, list[dict]] = {}
    for r in obs.revealed:
        by_stage.setdefault(r["stage"], []).append(r)
    stage = 0
    for h in obs.history:
        while stage < h["stage"]:
            stage += 1
            for r in by_stage.get(stage, []):
                post.reveal(r["component"], r["value"])
        if use_flow:
            post.observe_trade(h["action"], h["bid"], h["ask"])
    while stage < obs.stage:
        stage += 1
        for r in by_stage.get(stage, []):
            post.reveal(r["component"], r["value"])
    return post


class BayesAgent:
    def __init__(self, use_flow: bool = True, zero_profit: bool = False, name: str | None = None):
        self.use_flow = use_flow
        self.zero_profit = zero_profit
        self.name = name or (
            "glosten-milgrom" if zero_profit else ("bayes" if use_flow else "bayes-noflow")
        )

    def reset(self, game: Game) -> None:
        pass

    def act(self, obs: Observation) -> Quote:
        post = replay_posterior(obs, self.use_flow)
        w, mu = post.level_weights(), post.mean()
        fn = zero_profit_quote if self.zero_profit else optimal_quote
        bid, ask = fn(obs.game.levels, w, mu, obs.game.market, obs.bid_allowed, obs.ask_allowed)
        return Quote(bid, ask, {"mu": mu})


# Half-width of the ``bayes-mean`` quote in posterior standard deviations. Tuned by
# ``scripts/tune_k.py`` (argmax of edge captured against ``bayes``) on a tuning set with the
# core-v1 families, variants and generator (5 families x (4 classic + 8 perturbed) games, 2
# episodes each) but game seeds offset by 100000 and episode seeds 1000-1001, so disjoint from
# core-v1 and full-v1. Never tuned on core-v1 episodes. Argmax 1.40 (edge 85.6 on that set).
MEAN_K = 1.40


class MeanAgent:
    """Quotes the exact public posterior mean +/- ``k`` posterior sds (sd floored at one tick)."""

    def __init__(self, k: float = MEAN_K, name: str = "bayes-mean"):
        self.k = k
        self.name = name

    def reset(self, game: Game) -> None:
        pass

    def act(self, obs: Observation) -> Quote:
        post = replay_posterior(obs, True)
        mu = post.mean()
        sd = post.std()
        half = self.k * max(sd, obs.game.market.tick)
        bid = mu - half if obs.bid_allowed else None
        ask = mu + half if obs.ask_allowed else None
        return Quote(bid, ask, {"mu": mu, "sd": sd})


# Lookahead candidate grid: per side, the myopic price +/- LOOKAHEAD_STEPS steps of
# ``max(tick, round(sd / LOOKAHEAD_RES))`` where sd is the posterior sd. Coarse by design (the
# continuation value is smooth in the quote); the myopic quote itself is always a candidate, so
# the chosen quote's lookahead objective is never below the myopic quote's.
LOOKAHEAD_STEPS = 8
LOOKAHEAD_RES = 16.0


class LookaheadAgent:
    """One-step-lookahead quoter (exact probabilities, no sampling).

    Value of a quote ``(bid, ask)`` at step ``t``::

        ev_t(bid, ask) + sum over outcomes o in {buy, sell, no trade} of
            P(o) * E[ max over quotes of ev_{t+1} | posterior after o (and reveals) ]

    where the inner maximum is the myopic-optimal quote (``optimal_quote``) at ``t + 1`` with the
    inventory limits implied by the trade at ``t``, and, when ``t + 1`` opens a new stage, the
    expectation is also over the revealed components' values. The posterior update is
    ``Posterior.observe_trade``. Joint (bid, ask) candidates are searched on a grid around the
    myopic optimum (see ``LOOKAHEAD_STEPS``); the last step has no continuation, so it quotes
    the myopic optimum.
    """

    def __init__(
        self,
        name: str = "bayes-lookahead",
        steps: int = LOOKAHEAD_STEPS,
        res: float = LOOKAHEAD_RES,
    ):
        self.name = name
        self.steps = steps
        self.res = res
        self._game: Game | None = None
        self._groups: dict[int, tuple[np.ndarray, int]] = {}

    def reset(self, game: Game) -> None:
        self._game = game
        self._groups = {}

    def _reveal_groups(self, game: Game, stage: int) -> tuple[np.ndarray, int]:
        """Outcome -> id of the values revealed on entering ``stage`` (cached per game)."""
        if stage not in self._groups:
            comps = list(game.reveals[stage - 1])
            _, inv = np.unique(game.outcomes[:, comps], axis=0, return_inverse=True)
            inv = np.asarray(inv).reshape(-1)
            self._groups[stage] = (inv, int(inv.max()) + 1)
        return self._groups[stage]

    @staticmethod
    def _myopic_ev(game: Game, w_out: np.ndarray, allow_bid: bool, allow_ask: bool) -> float:
        levels = game.levels
        w = np.bincount(game.level_index, weights=w_out, minlength=len(levels))
        mu = float(w_out @ game.value)
        bid, ask = optimal_quote(levels, w, mu, game.market, allow_bid, allow_ask)
        return quote_value(levels, w, mu, bid, ask, game.market).ev

    def _continuation(self, game: Game, post: Posterior, step: int, position: int) -> float:
        """Expected myopic-optimal ev at ``step + 1`` given the posterior after step ``step``."""
        lim = game.market.inventory_limit
        allow_bid, allow_ask = position < lim, position > -lim
        nxt = step + 1
        stage = game.stage_of(nxt)
        if stage == game.stage_of(step):
            return self._myopic_ev(game, post.w, allow_bid, allow_ask)
        inv, n = self._reveal_groups(game, stage)
        mass = np.bincount(inv, weights=post.w, minlength=n)
        total = 0.0
        for g in np.flatnonzero(mass > 1e-12):
            w_g = post.w * (inv == g) / mass[g]
            total += mass[g] * self._myopic_ev(game, w_g, allow_bid, allow_ask)
        return total

    def act(self, obs: Observation) -> Quote:
        game, m = obs.game, obs.game.market
        post = replay_posterior(obs, True)
        levels, w, mu = game.levels, post.level_weights(), post.mean()
        b0, a0 = optimal_quote(levels, w, mu, m, obs.bid_allowed, obs.ask_allowed)
        has_next = obs.step + 1 < game.n_steps
        if not has_next:
            return Quote(b0, a0, {"mu": mu, "lookahead": 0.0})

        h = max(m.tick, round(post.std() / self.res / m.tick) * m.tick)
        offsets = np.arange(-self.steps, self.steps + 1) * h
        bids = [None] if b0 is None else sorted({round(float(b0 + o), 10) for o in offsets})
        asks = [None] if a0 is None else sorted({round(float(a0 + o), 10) for o in offsets})

        def branch(action: str, bid: float | None, ask: float | None):
            """(probability, posterior-after) of a trade outcome, or None if impossible."""
            pb, ps = taker_probs(levels, mu, bid, ask, m)
            lik = {"buy": pb, "sell": ps, None: 1.0 - pb - ps}[action]
            prob = float(w @ np.clip(lik, 0.0, 1.0))
            if prob <= 1e-12:
                return None
            nxt = post.copy()
            nxt.observe_trade(action, bid, ask)
            return prob, nxt

        pos = obs.position
        buy_cont: dict[float, float] = {}
        sell_cont: dict[float, float] = {}
        for a in asks:
            if a is not None:
                br = branch("buy", None, a)
                buy_cont[a] = (
                    0.0
                    if br is None
                    else br[0] * self._continuation(game, br[1], obs.step, pos - 1)
                )
        for b in bids:
            if b is not None:
                br = branch("sell", b, None)
                sell_cont[b] = (
                    0.0
                    if br is None
                    else br[0] * self._continuation(game, br[1], obs.step, pos + 1)
                )

        best: tuple[float, float | None, float | None] | None = None
        for b in bids:
            for a in asks:
                if b is not None and a is not None and b > a:
                    continue
                value = quote_value(levels, w, mu, b, a, m).ev
                if a is not None:
                    value += buy_cont[a]
                if b is not None:
                    value += sell_cont[b]
                br = branch(None, b, a)
                if br is not None:
                    value += br[0] * self._continuation(game, br[1], obs.step, pos)
                if best is None or value > best[0] + 1e-12:
                    best = (value, b, a)
        assert best is not None
        return Quote(best[1], best[2], {"mu": mu, "lookahead": best[0]})


class StaticAgent:
    """Quotes prior mean +/- ``k`` prior standard deviations for the whole game."""

    def __init__(self, k: float = 1.0, name: str = "static"):
        self.k = k
        self.name = name

    def reset(self, game: Game) -> None:
        pass

    def act(self, obs: Observation) -> Quote:
        g = obs.game
        half = self.k * g.prior_std
        return Quote(g.prior_mean - half, g.prior_mean + half)


class RandomAgent:
    """Random mid within one prior sd of the prior mean, random width up to two prior sds."""

    def __init__(self, seed: int = 0, name: str = "random"):
        self.seed = seed
        self.name = name
        self._rng = np.random.default_rng(seed)

    def reset(self, game: Game) -> None:
        self._rng = np.random.default_rng([self.seed, game.seed or 0])

    def act(self, obs: Observation) -> Quote:
        g = obs.game
        mid = g.prior_mean + g.prior_std * self._rng.uniform(-1, 1)
        half = g.prior_std * self._rng.uniform(0.05, 1.0)
        return Quote(mid - half, mid + half)


BASELINES = {
    "bayes": lambda: BayesAgent(),
    "bayes-noflow": lambda: BayesAgent(use_flow=False),
    "bayes-mean": lambda: MeanAgent(),
    "bayes-lookahead": lambda: LookaheadAgent(),
    "glosten-milgrom": lambda: BayesAgent(zero_profit=True),
    "static": lambda: StaticAgent(),
    "random": lambda: RandomAgent(),
}
