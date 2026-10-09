"""Reference market makers with white-box access to the game.

- ``bayes``: exact public posterior, myopic profit-maximising quote. The reference score.
- ``bayes-noflow``: same, but its belief ignores order flow (updates on reveals only). The gap
  to ``bayes`` is the value of learning from fills.
- ``glosten-milgrom``: exact posterior, zero-profit (competitive) quote. Expected P&L ~ 0; a
  check on the simulator and a reminder that a tight market is not a profitable one.
- ``static``: prior mean +/- one prior standard deviation, never updated.
- ``random``: random mid and width around the prior. A floor.
"""

from __future__ import annotations

import numpy as np

from mmarena.agents.base import Observation, Quote
from mmarena.games.base import Game
from mmarena.market import Posterior, optimal_quote, zero_profit_quote


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
    "glosten-milgrom": lambda: BayesAgent(zero_profit=True),
    "static": lambda: StaticAgent(),
    "random": lambda: RandomAgent(),
}
