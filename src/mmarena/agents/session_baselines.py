"""Reference market makers for session suites (suite format 2).

All quote from exact posteriors rebuilt from the observation (``replay``); none keeps state
between quotes except a seeded random stream (``bayes-thompson``, ``random``).

- ``oracle``: told the true informed share (``privileged``); myopic optimum for it. The
  100-point anchor of the score.
- ``bayes``: exact public joint posterior, myopic optimum. The per-state reference.
- ``bayes-lookahead`` (and ``-w2``, ``-w4``, ``-w8``): immediate expected profit plus ``weight``
  times the expected myopic-optimal profit of the next quote, across fills, reveals and the
  settlement. Weight 1 is plain one-step lookahead; a larger weight values what a quote
  teaches about the regime on more than one later quote.
- ``bayes-optimist``: myopic optimum after tilting the regime weights toward the profitable
  regimes, ``w_k * exp(gamma * v_k / max v)``, with ``v_k`` the oracle's round-start value
  under regime ``k``. A cheap exploring heuristic.
- ``bayes-thompson``: samples a regime from the posterior at each round start and quotes as the
  oracle would for it.
- ``bayes-nolearn``: exact value belief from reveals and flow given each regime, regime weights
  kept at the prior. The gap to ``bayes`` is the value of learning the regime.
- ``bayes-fixed-low``, ``bayes-fixed-high``: core-v1's Bayes quoter with the informed share
  assumed to be the lowest or highest regime.
- ``bayes-noflow``: reveals and settlements only, no order flow.
- ``bayes-mean``: exact public mean +/- ``MEAN_K_V2`` public sds.
- ``glosten-milgrom``: zero-profit quote under the exact public posterior.
- ``static``: prior mean +/- one prior sd. ``random``: random mid and width around the prior.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable

import numpy as np

from mmarena import joint
from mmarena.agents.base import Quote
from mmarena.engine import _to_tick
from mmarena.market import BUY, SELL
from mmarena.sessions import SessionObservation, SessionSpec

# Half-width of ``bayes-mean`` in public posterior sds and the tilt of ``bayes-optimist``. Both
# are tuned by ``scripts/tune_v2.py`` (pooled share of the oracle on 60 open (noise ratio 0.85)
# and 60 mixed (0.7) sessions at game seeds 131000-135299, disjoint from every released suite):
# argmax k 1.0 (65.9) over 0.6-2.4, argmax gamma 1 (87.9) over {0.5, 1, 2, 4, 8}.
MEAN_K_V2 = 1.0
OPTIMIST_GAMMA = 1.0
# Lookahead candidates: the myopic half-width on each side times these factors (plus the
# myopic quote itself).
LOOKAHEAD_MULTS = (0.5, 0.65, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0)


class PinnedPosterior(joint.JointPosterior):
    """Exact value belief given each regime, with the regime weights held at the prior."""

    def _normalise(self, what: str) -> None:
        rows = self.w.sum(axis=1, keepdims=True)
        if np.any(rows <= 0):
            raise ValueError(f"a regime row collapsed after {what}")
        self.w = self.w / rows * self.regimes.prior[:, None]

    def settle(self, value: float) -> None:
        self.start_round()


class NoFlowPosterior(joint.JointPosterior):
    """Updates on reveals and settlements only; order flow is ignored."""

    def observe_trade(self, action: str | None, bid: float | None, ask: float | None) -> None:
        return None


def replay(obs: SessionObservation, post: joint.JointPosterior) -> joint.JointPosterior:
    """Apply the session's public history to ``post`` (fresh) and return it."""
    rows: dict[int, list[dict]] = {}
    for h in obs.history:
        rows.setdefault(h["round"], []).append(h)

    def reveal_through(revealed, stage_from: int, stage_to: int) -> None:
        for x in revealed:
            if stage_from < x["stage"] <= stage_to:
                post.reveal(x["component"], x["value"])

    for r in range(obs.round + 1):
        current = r == obs.round
        revealed = obs.revealed if current else obs.settled[r]["revealed"]
        stage = 0
        for h in rows.get(r, []):
            if h["stage"] > stage:
                reveal_through(revealed, stage, h["stage"])
                stage = h["stage"]
            post.observe_trade(h["action"], h["bid"], h["ask"])
        if current:
            reveal_through(revealed, stage, obs.stage)
        else:
            reveal_through(revealed, stage, obs.spec.game.n_stages)
            post.settle(obs.settled[r]["value"])
    return post


class SessionBayes:
    """Myopic quoter on a posterior: ``rule`` is ``opt`` (optimum), ``gm`` or ``mean``."""

    def __init__(
        self,
        name: str = "bayes",
        rule: str = "opt",
        belief: Callable[[SessionSpec], joint.JointPosterior] | None = None,
        k: float = MEAN_K_V2,
    ) -> None:
        self.name, self.rule, self.k = name, rule, k
        self._belief = belief or (lambda spec: joint.JointPosterior(spec.game, spec.regimes))
        self.spec: SessionSpec | None = None

    def reset(self, spec: SessionSpec) -> None:
        self.spec = spec

    def act(self, obs: SessionObservation) -> Quote:
        post = replay(obs, self._belief(obs.spec))
        g, m = obs.game, obs.game.market
        mu = post.mean()
        if self.rule == "mean":
            half = self.k * max(post.std(), m.tick)
            bid = mu - half if obs.bid_allowed else None
            ask = mu + half if obs.ask_allowed else None
            return Quote(bid, ask, {"mu": mu})
        fn = joint.optimal_quote if self.rule == "opt" else joint.zero_profit_quote
        bid, ask = fn(
            g.levels,
            post.level_weights(),
            mu,
            post.alpha,
            m.noise_scale,
            m.tick,
            obs.bid_allowed,
            obs.ask_allowed,
        )
        return Quote(bid, ask, {"mu": mu})


def _fixed(alpha_index: int) -> Callable[[SessionSpec], joint.JointPosterior]:
    def make(spec: SessionSpec) -> joint.JointPosterior:
        a = float(spec.regimes.alpha[alpha_index])
        return joint.JointPosterior(spec.game, joint.Regimes.of([a]))

    return make


class OracleAgent:
    """Told the true regime; quotes the myopic optimum given it (noise centre: public mean)."""

    privileged = True

    def __init__(self, name: str = "oracle") -> None:
        self.name = name
        self.regime: int | None = None

    def reset(self, spec: SessionSpec) -> None:
        self.regime = None

    def set_regime(self, k: int) -> None:
        self.regime = int(k)

    def act(self, obs: SessionObservation) -> Quote:
        if self.regime is None:
            raise RuntimeError("the oracle was not given the regime")
        post = replay(obs, joint.JointPosterior(obs.game, obs.spec.regimes))
        wk, ak = post.conditional(self.regime)
        m = obs.game.market
        bid, ask = joint.optimal_quote(
            obs.game.levels, wk, post.mean(), ak, m.noise_scale, m.tick,
            obs.bid_allowed, obs.ask_allowed,
        )  # fmt: skip
        return Quote(bid, ask)


def round_start_curves(spec: SessionSpec) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-regime one-step profit of every grid price at a round start: ``(grid, bid, ask)``.

    At a round start the value belief is the prior whatever the regime, so the profit under
    regime weights ``wt`` is ``wt @ curve`` on each side.
    """
    g, m = spec.game, spec.game.market
    p0 = np.bincount(g.level_index, weights=g.prob, minlength=len(g.levels))
    mu0 = g.prior_mean
    grid = joint.price_grid(g.levels, mu0, m.noise_scale, m.tick)
    bid = np.array(
        [
            joint.side_values(g.levels, p0[None, :], mu0, [a], m.noise_scale, grid, SELL)
            for a in spec.regimes.alpha
        ]
    )
    ask = np.array(
        [
            joint.side_values(g.levels, p0[None, :], mu0, [a], m.noise_scale, grid, BUY)
            for a in spec.regimes.alpha
        ]
    )
    return grid, bid, ask


class OptimistAgent:
    """Myopic optimum under regime weights tilted toward the profitable regimes."""

    def __init__(self, gamma: float = OPTIMIST_GAMMA, name: str = "bayes-optimist") -> None:
        self.gamma, self.name = gamma, name
        self.tilt: np.ndarray | None = None

    def reset(self, spec: SessionSpec) -> None:
        _, bid, ask = round_start_curves(spec)
        v = bid.max(axis=1) + ask.max(axis=1)
        self.tilt = np.exp(self.gamma * v / max(float(v.max()), 1e-12))

    def act(self, obs: SessionObservation) -> Quote:
        assert self.tilt is not None
        post = replay(obs, joint.JointPosterior(obs.game, obs.spec.regimes))
        wl = post.level_weights() * self.tilt[:, None]
        m = obs.game.market
        bid, ask = joint.optimal_quote(
            obs.game.levels, wl / wl.sum(), post.mean(), post.alpha, m.noise_scale, m.tick,
            obs.bid_allowed, obs.ask_allowed,
        )  # fmt: skip
        return Quote(bid, ask)


class ThompsonAgent:
    """Samples a regime from the public posterior at each round start; quotes as the oracle."""

    def __init__(self, name: str = "bayes-thompson") -> None:
        self.name = name
        self._rng: np.random.Generator | None = None
        self._round, self._k = -1, 0

    def reset(self, spec: SessionSpec) -> None:
        self._rng, self._round = None, -1

    def act(self, obs: SessionObservation) -> Quote:
        if self._rng is None:
            self._rng = np.random.default_rng(
                [zlib.crc32(obs.session_id.encode()), obs.episode_seed, 7]
            )
        post = replay(obs, joint.JointPosterior(obs.game, obs.spec.regimes))
        rw = post.regime_weights()
        if obs.round != self._round:
            self._round = obs.round
            self._k = int(self._rng.choice(len(rw), p=rw / rw.sum()))
        k = self._k if rw[self._k] > 0 else int(np.argmax(rw))
        wk, ak = post.conditional(k)
        m = obs.game.market
        bid, ask = joint.optimal_quote(
            obs.game.levels, wk, post.mean(), ak, m.noise_scale, m.tick,
            obs.bid_allowed, obs.ask_allowed,
        )  # fmt: skip
        return Quote(bid, ask, {"regime_sample": k})


def _myopic_ev(post: joint.JointPosterior, allow_bid: bool, allow_ask: bool) -> float:
    g, m = post.game, post.game.market
    wl, mu = post.level_weights(), post.mean()
    bid, ask = joint.optimal_quote(
        g.levels, wl, mu, post.alpha, m.noise_scale, m.tick, allow_bid, allow_ask
    )
    return joint.quote_value(g.levels, wl, mu, bid, ask, post.alpha, m.noise_scale).ev


class LookaheadAgent:
    """Immediate expected profit plus ``weight`` x the expected myopic-optimal profit next.

    The next quote's value is exact across the three trade outcomes, the reveal (when the next
    quote opens a stage) and the settlement value with its regime update (when it opens a
    round). Candidates are the myopic quote and, per side, the myopic half-width around the
    public mean times ``LOOKAHEAD_MULTS``. The session's last quote is the myopic optimum.
    """

    def __init__(self, weight: float = 1.0, name: str | None = None) -> None:
        self.weight = float(weight)
        self.name = name or (
            "bayes-lookahead" if self.weight == 1 else f"bayes-lookahead-w{self.weight:g}"
        )
        self.spec: SessionSpec | None = None

    def reset(self, spec: SessionSpec) -> None:
        self.spec = spec
        _, self._c_bid, self._c_ask = round_start_curves(spec)
        g = spec.game
        if g.reveals:
            _, inv = np.unique(g.outcomes[:, list(g.reveals[0])], axis=0, return_inverse=True)
            self._groups = np.asarray(inv).reshape(-1)
        else:
            self._groups = np.zeros(len(g.prob), dtype=int)

    def _continuation(self, post: joint.JointPosterior, obs: SessionObservation, pos: int) -> float:
        spec = obs.spec
        g = spec.game
        lim = g.market.inventory_limit
        nxt = obs.step + 1
        if nxt < spec.steps_per_round:
            allow = (pos < lim, pos > -lim)
            if g.stage_of(nxt) == obs.stage:
                return _myopic_ev(post, *allow)
            total = 0.0
            for j in range(int(self._groups.max()) + 1):
                mask = self._groups == j
                mass = float(post.w[:, mask].sum())
                if mass <= 1e-12:
                    continue
                branch = post.copy()
                branch.w = post.w * mask[None, :] / mass
                total += mass * _myopic_ev(branch, *allow)
            return total
        if obs.round + 1 >= spec.rounds:
            return 0.0
        wl = post.level_weights()
        pl = wl.sum(axis=0)
        ok = pl > 1e-12
        wt = wl[:, ok] / pl[ok]  # regime weights after settling at each value
        vals = (wt.T @ self._c_bid).max(axis=1) + (wt.T @ self._c_ask).max(axis=1)
        return float(pl[ok] @ vals)

    def act(self, obs: SessionObservation) -> Quote:
        g, m = obs.game, obs.game.market
        post = replay(obs, joint.JointPosterior(g, obs.spec.regimes))
        levels, wl, mu, s, tick = g.levels, post.level_weights(), post.mean(), m.noise_scale, m.tick
        alpha = post.alpha
        allow = (obs.bid_allowed, obs.ask_allowed)
        b0, a0 = joint.optimal_quote(levels, wl, mu, alpha, s, tick, *allow)
        if obs.quotes_left <= 1:
            return Quote(b0, a0, {"mu": mu})
        asks: list[float | None] = [None]
        bids: list[float | None] = [None]
        if a0 is not None:
            asks = sorted(
                {_to_tick(mu + max(a0 - mu, tick) * f, tick, True) for f in LOOKAHEAD_MULTS} | {a0}
            )
        if b0 is not None:
            bids = sorted(
                {_to_tick(mu - max(mu - b0, tick) * f, tick, False) for f in LOOKAHEAD_MULTS} | {b0}
            )

        def branch(action: str | None, bid: float | None, ask: float | None) -> float:
            pb, ps = joint.fill_probs(levels, mu, bid, ask, alpha, s)
            lik = pb if action == BUY else ps if action == SELL else 1.0 - pb - ps
            prob = float((wl * np.clip(lik, 0.0, 1.0)).sum())
            if prob <= 1e-12:
                return 0.0
            nxt = post.copy()
            nxt.observe_trade(action, bid, ask)
            pos = obs.position + (-1 if action == BUY else 1 if action == SELL else 0)
            return prob * self._continuation(nxt, obs, pos)

        buy_c = {a: branch(BUY, None, a) for a in asks if a is not None}
        sell_c = {b: branch(SELL, b, None) for b in bids if b is not None}
        best: tuple[float, float | None, float | None] | None = None
        for b in bids:
            for a in asks:
                if b is not None and a is not None and b > a:
                    continue
                v = joint.quote_value(levels, wl, mu, b, a, alpha, s).ev
                cont = buy_c.get(a, 0.0) + sell_c.get(b, 0.0) + branch(None, b, a)
                v += self.weight * cont
                if best is None or v > best[0] + 1e-12:
                    best = (v, b, a)
        assert best is not None
        return Quote(best[1], best[2], {"mu": mu, "lookahead": best[0]})


class StaticSession:
    """Prior mean +/- ``k`` prior sds at every quote."""

    def __init__(self, k: float = 1.0, name: str = "static") -> None:
        self.k, self.name = k, name

    def reset(self, spec: SessionSpec) -> None:
        pass

    def act(self, obs: SessionObservation) -> Quote:
        g = obs.game
        return Quote(g.prior_mean - self.k * g.prior_std, g.prior_mean + self.k * g.prior_std)


class RandomSession:
    """Random mid within one prior sd of the prior mean, random width up to two prior sds."""

    def __init__(self, seed: int = 0, name: str = "random") -> None:
        self.seed, self.name = seed, name
        self._rng: np.random.Generator | None = None

    def reset(self, spec: SessionSpec) -> None:
        self._rng = None

    def act(self, obs: SessionObservation) -> Quote:
        if self._rng is None:
            self._rng = np.random.default_rng(
                [self.seed, zlib.crc32(obs.session_id.encode()), obs.episode_seed]
            )
        g = obs.game
        mid = g.prior_mean + g.prior_std * self._rng.uniform(-1, 1)
        half = g.prior_std * self._rng.uniform(0.05, 1.0)
        return Quote(mid - half, mid + half)


SESSION_BASELINES: dict[str, Callable[[], object]] = {
    "oracle": lambda: OracleAgent(),
    "bayes": lambda: SessionBayes(),
    "bayes-lookahead": lambda: LookaheadAgent(1.0),
    "bayes-lookahead-w2": lambda: LookaheadAgent(2.0),
    "bayes-lookahead-w4": lambda: LookaheadAgent(4.0),
    "bayes-lookahead-w8": lambda: LookaheadAgent(8.0),
    "bayes-optimist": lambda: OptimistAgent(),
    "bayes-thompson": lambda: ThompsonAgent(),
    "bayes-nolearn": lambda: SessionBayes(
        "bayes-nolearn", belief=lambda spec: PinnedPosterior(spec.game, spec.regimes)
    ),
    "bayes-fixed-low": lambda: SessionBayes("bayes-fixed-low", belief=_fixed(0)),
    "bayes-fixed-high": lambda: SessionBayes("bayes-fixed-high", belief=_fixed(-1)),
    "bayes-noflow": lambda: SessionBayes(
        "bayes-noflow", belief=lambda spec: NoFlowPosterior(spec.game, spec.regimes)
    ),
    "bayes-mean": lambda: SessionBayes("bayes-mean", rule="mean"),
    "glosten-milgrom": lambda: SessionBayes("glosten-milgrom", rule="gm"),
    "static": lambda: StaticSession(),
    "random": lambda: RandomSession(),
}
