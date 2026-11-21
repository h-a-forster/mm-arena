"""Per-session metrics from version-3 traces (session suites).

Every quantity is a sum over the session's quotes, in prior-sd units of the session's game, so
sessions of different games pool on one scale. The score of a set of sessions is
``100 * sum(xpnl_alpha) / sum(oracle)``, where ``oracle`` is the known-regime oracle's own
``ev_alpha`` total on the same session and seed.

Shortfall identity (exact for every session)::

    oracle - xpnl_alpha = pricing + information + path + residual

- ``pricing``: sum of ``bayes_ev - ev``, what the agent's quotes gave up against the myopic
  Bayes quote given public information (zero for a myopic Bayes quoter; an explorer pays here
  on purpose);
- ``information``: sum of ``oracle_ev_alpha - bayes_ev_alpha`` at the agent's states, what not
  knowing the regime still costs after what the agent's own quoting has revealed;
- ``path``: the oracle's own total minus its value at the agent's states;
- ``residual``: sum of ``(bayes_ev_alpha - bayes_ev) - (ev_alpha - ev)``, the difference in
  regime luck between the Bayes quote and the agent's quote at the same states; zero in
  expectation for any quote rule that uses public information only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from mmarena.metrics import _step_usage

Key = tuple[str, int]


def session_key(trace: Mapping[str, Any]) -> Key:
    return trace["session"]["id"], int(trace["seed"])


def _half(bid: float | None, ask: float | None) -> float | None:
    return None if bid is None or ask is None else 0.5 * (ask - bid)


@dataclass
class SessionMetrics:
    agent: str
    key: Key
    family: str
    tier: str
    regime: int
    alpha: float
    sd: float
    n_quotes: int
    xpnl_alpha: float
    xpnl: float
    pnl: float
    bayes_xpnl: float
    bayes_xpnl_alpha: float
    oracle_local: float
    pricing: float
    residual: float
    round_xpnl_alpha: list[float]
    alpha_mass: list[float]  # posterior mass on the true regime at each round start
    # half-widths (prior sd) at the quotes where the agent and both references are two-sided
    half: list[float] = field(default_factory=list)  # the agent's quote
    half_bayes: list[float] = field(default_factory=list)  # the myopic Bayes quote
    half_prior: list[float] = field(default_factory=list)  # the prior-regime quote
    width: float = 0.0
    bayes_width: float = 0.0
    n_width: int = 0
    early_tighter: int = 0
    early_two_sided: int = 0
    mid_err: float = 0.0
    n_mid: int = 0
    invalid: int = 0
    no_quote: int = 0
    tokens: float = 0.0
    output_tokens: float = 0.0
    cost_usd: float | None = 0.0

    @property
    def information(self) -> float:
        return self.oracle_local - self.bayes_xpnl_alpha


def session_metrics(trace: Mapping[str, Any]) -> SessionMetrics:
    s = trace["session"]
    sd = float(s["game"]["prior_std"])
    tick = float(s["game"]["market"]["tick"])
    k = int(s["regime"])
    steps = trace["steps"]
    m = SessionMetrics(
        agent=trace["agent"],
        key=session_key(trace),
        family=s["family"],
        tier=s["tier"],
        regime=k,
        alpha=float(s["alpha"]),
        sd=sd,
        n_quotes=len(steps),
        xpnl_alpha=trace["xpnl_alpha"] / sd,
        xpnl=trace["xpnl"] / sd,
        pnl=trace["pnl"] / sd,
        bayes_xpnl=trace["bayes_xpnl_local"] / sd,
        bayes_xpnl_alpha=trace["bayes_xpnl_alpha_local"] / sd,
        oracle_local=trace["oracle_xpnl_alpha_local"] / sd,
        pricing=sum(x["bayes_ev"] - x["ev"] for x in steps) / sd,
        residual=sum(
            (x["bayes_ev_alpha"] - x["bayes_ev"]) - (x["ev_alpha"] - x["ev"]) for x in steps
        )
        / sd,
        round_xpnl_alpha=[r["xpnl_alpha"] / sd for r in trace["rounds"]],
        alpha_mass=[float(r["alpha_w_start"][k]) for r in trace["rounds"]],
    )
    cost: float | None = 0.0
    for x in steps:
        h = _half(x["bid"], x["ask"])
        hb = _half(x["bayes_bid"], x["bayes_ask"])
        hp = _half(x["prior_bid"], x["prior_ask"])
        if h is not None and hb is not None and hp is not None:
            m.half.append(h / sd)
            m.half_bayes.append(hb / sd)
            m.half_prior.append(hp / sd)
        if h is not None and hb is not None:
            m.width += 2 * h / sd
            m.bayes_width += 2 * hb / sd
            m.n_width += 1
            if x["round"] < 2:
                m.early_two_sided += 1
                m.early_tighter += h < hb - 1e-9
        if h is not None and x["sd"] > 0:
            # floored at the tick as in core-v1: once a reveal fixes the value, sd is rounding noise
            m.mid_err += abs(0.5 * (x["bid"] + x["ask"]) - x["mu"]) / max(x["sd"], tick)
            m.n_mid += 1
        if x["invalid"]:
            m.invalid += 1
        if x["bid"] is None and x["ask"] is None:
            m.no_quote += 1
        info = x.get("info") or {}
        if "usage" in info:
            tokens, c = _step_usage(info)
            m.tokens += tokens or 0.0
            m.output_tokens += float(info["usage"].get("output_tokens", 0) or 0)
            cost = None if cost is None or c is None else cost + c
    m.cost_usd = cost
    return m


def select_ok(traces: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Completed sessions only, the last attempt of each (session, seed) per agent."""
    last: dict[tuple[str, Key], dict[str, Any]] = {}
    for t in traces:
        if t.get("status") == "ok":
            last[(t["agent"], session_key(t))] = dict(t)
    return list(last.values())
