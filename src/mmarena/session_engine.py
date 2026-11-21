"""Session simulator: one session, one market maker, trace version 3.

Randomness (each round's hidden outcome, who arrives at each quote and the noise traders'
valuation shocks) is drawn up front from ``(session id, seed)``; the true regime is fixed by the
suite. Every agent playing the same session and seed therefore faces the same outcomes and the
same counterparties (common random numbers).

Each quote is scored with two exact one-step expectations:

- ``ev``: given public information (the joint posterior over regime and outcome);
- ``ev_alpha``: given public information and the session's true informed share.

Both are unbiased for realised profit for any quote rule that uses public information only;
``ev_alpha`` is also unbiased for the ``oracle``, which is told the regime, and is the score.
At every state the step also records three reference quotes computed from the same posterior:
the myopic Bayes quote (``bayes_*``), the known-regime oracle's quote (``oracle_*``) and the
myopic quote with the regime belief reset to the prior (``prior_*``, for the learning
diagnostic).
"""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from mmarena import joint
from mmarena.agents.base import Agent, AgentError, InfraError
from mmarena.engine import _clean_side, _jsonable, _to_tick, provenance
from mmarena.market import BUY, SELL
from mmarena.sessions import Session, SessionObservation, session_rng

# 3: session traces (suite format 2). ``session`` replaces ``game``; per-round records; each
#    step carries ``ev`` and ``ev_alpha`` and the reference quotes.
TRACE_VERSION = 3


def draw_session(session: Session, seed: int) -> dict[str, np.ndarray]:
    """Pre-draw all exogenous randomness of a session."""
    rng = session_rng(session, seed)
    g, r, n = session.game, session.spec.rounds, session.spec.steps_per_round
    return {
        "omega": rng.choice(len(g.prob), size=r, p=g.prob),
        "u": rng.random((r, n)),  # informed if u < alpha
        "z": rng.standard_normal((r, n)),  # noise-trader valuation shock
    }


def _prior_reset(post: joint.JointPosterior) -> np.ndarray:
    """Joint level weights with the public value belief and the regime belief at the prior."""
    return post.regimes.prior[:, None] * post.level_weights().sum(axis=0)[None, :]


class _Stop(Exception):
    pass


def run_session(session: Session, agent: Agent, seed: int) -> dict[str, Any]:
    """Play one session and return its full trace (JSON-serialisable)."""
    spec, game = session.spec, session.game
    m, levels, k_true = game.market, game.levels, session.regime
    alpha, s, tick = spec.regimes.alpha, m.noise_scale, m.tick
    draws = draw_session(session, seed)
    post = joint.JointPosterior(game, spec.regimes)
    history: list[dict[str, Any]] = []
    settled: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    rounds: list[dict[str, Any]] = []
    status, error = "ok", None
    agent.reset(spec)  # type: ignore[arg-type]
    if getattr(agent, "privileged", False):
        agent.set_regime(k_true)  # type: ignore[attr-defined]

    try:
        for r in range(spec.rounds):
            omega = int(draws["omega"][r])
            v_true = float(game.value[omega])
            revealed: list[dict[str, Any]] = []
            position, cash = 0, 0.0
            start_w = post.alpha_w.tolist()
            for t in range(spec.steps_per_round):
                stage = game.stage_of(t)
                if t > 0 and stage != game.stage_of(t - 1):
                    for c in game.reveals[stage - 1]:
                        val = float(game.outcomes[omega, c])
                        post.reveal(c, val)
                        name = game.components[c]
                        revealed.append(
                            {"stage": stage, "component": c, "name": name, "value": val}
                        )
                bid_allowed = position < m.inventory_limit
                ask_allowed = position > -m.inventory_limit
                obs = SessionObservation(
                    spec=spec,
                    session_id=session.id,
                    round=r,
                    step=t,
                    stage=stage,
                    revealed=tuple(dict(x) for x in revealed),
                    history=tuple(dict(h) for h in history),
                    settled=tuple(dict(x) for x in settled),
                    position=position,
                    cash=cash,
                    bid_allowed=bid_allowed,
                    ask_allowed=ask_allowed,
                    episode_seed=int(seed),
                )
                started = time.perf_counter()
                invalid = None
                info: dict[str, Any] = {}
                try:
                    q = agent.act(obs)  # type: ignore[arg-type]
                    info = dict(q.info)
                    bid_q, ask_q = _clean_side(q.bid), _clean_side(q.ask)
                except InfraError as exc:
                    status, error = "error", f"infra: {exc}"
                    raise _Stop from exc
                except AgentError as exc:
                    bid_q = ask_q = None
                    invalid = "format"
                    info = {"error": str(exc), **getattr(exc, "info", {})}
                except Exception as exc:  # noqa: BLE001 - an agent crash is the agent's fault
                    bid_q = ask_q = None
                    invalid = "exception"
                    info = {"error": f"{type(exc).__name__}: {exc}"}
                latency = time.perf_counter() - started

                bid = None if bid_q is None else _to_tick(bid_q, tick, up=False)
                ask = None if ask_q is None else _to_tick(ask_q, tick, up=True)
                if (bid is not None and not math.isfinite(bid)) or (
                    ask is not None and not math.isfinite(ask)
                ):
                    bid = ask = None
                    invalid = invalid or "nonfinite"
                if bid is not None and ask is not None and bid > ask:
                    bid = ask = None
                    invalid = invalid or "crossed"
                pulled = []
                if bid is not None and not bid_allowed:
                    bid, pulled = None, [*pulled, "bid"]
                if ask is not None and not ask_allowed:
                    ask, pulled = None, [*pulled, "ask"]

                wl, mu, sd = post.level_weights(), post.mean(), post.std()
                support = levels[wl.sum(axis=0) > 0]
                wk, ak = post.conditional(k_true)
                allow = (bid_allowed, ask_allowed)
                qv = joint.quote_value(levels, wl, mu, bid, ask, alpha, s)
                qa = joint.quote_value(levels, wk, mu, bid, ask, ak, s)
                b_bid, b_ask = joint.optimal_quote(levels, wl, mu, alpha, s, tick, *allow)
                o_bid, o_ask = joint.optimal_quote(levels, wk, mu, ak, s, tick, *allow)
                p_bid, p_ask = joint.optimal_quote(
                    levels, _prior_reset(post), mu, alpha, s, tick, *allow
                )

                b_qv = joint.quote_value(levels, wl, mu, b_bid, b_ask, alpha, s)
                b_qa = joint.quote_value(levels, wk, mu, b_bid, b_ask, ak, s)
                o_qa = joint.quote_value(levels, wk, mu, o_bid, o_ask, ak, s)

                informed = draws["u"][r, t] < alpha[k_true]
                valuation = v_true if informed else mu + s * draws["z"][r, t]
                action, price = None, None
                if ask is not None and valuation > ask:
                    action, price = BUY, ask
                    position -= 1
                    cash += ask
                elif bid is not None and valuation < bid:
                    action, price = SELL, bid
                    position += 1
                    cash -= bid
                alpha_w = post.regime_weights().tolist()
                post.observe_trade(action, bid, ask)

                history.append(
                    {
                        "round": r,
                        "step": t,
                        "stage": stage,
                        "bid": bid,
                        "ask": ask,
                        "action": action,
                        "price": price,
                    }
                )
                steps.append(
                    {
                        "t": len(steps),
                        "round": r,
                        "step": t,
                        "stage": stage,
                        "bid_quoted": bid_q,
                        "ask_quoted": ask_q,
                        "bid": bid,
                        "ask": ask,
                        "invalid": invalid,
                        "pulled": pulled,
                        "bid_allowed": bid_allowed,
                        "ask_allowed": ask_allowed,
                        "mu": mu,
                        "sd": sd,
                        "lo": float(support[0]),
                        "hi": float(support[-1]),
                        "alpha_w": alpha_w,
                        "p_buy": qv.p_buy,
                        "p_sell": qv.p_sell,
                        "ev": qv.ev,
                        "capture": qv.capture,
                        "adverse": qv.adverse,
                        "ev_alpha": qa.ev,
                        "capture_alpha": qa.capture,
                        "adverse_alpha": qa.adverse,
                        "bayes_bid": b_bid,
                        "bayes_ask": b_ask,
                        "bayes_ev": b_qv.ev,
                        "bayes_ev_alpha": b_qa.ev,
                        "oracle_bid": o_bid,
                        "oracle_ask": o_ask,
                        "oracle_ev_alpha": o_qa.ev,
                        "prior_bid": p_bid,
                        "prior_ask": p_ask,
                        "taker": "informed" if informed else "noise",
                        "action": action,
                        "price": price,
                        "position": position,
                        "cash": cash,
                        "mu_after": post.mean(),
                        "latency_s": round(latency, 4),
                        "info": info,
                    }
                )
            mine = [x for x in steps if x["round"] == r]
            rounds.append(
                {
                    "round": r,
                    "hidden": {
                        name: float(game.outcomes[omega, i])
                        for i, name in enumerate(game.components)
                    },
                    "value": v_true,
                    "revealed": revealed,
                    "alpha_w_start": start_w,
                    "position": position,
                    "pnl": cash + position * v_true,
                    "xpnl": float(sum(x["ev"] for x in mine)),
                    "xpnl_alpha": float(sum(x["ev_alpha"] for x in mine)),
                    "oracle_xpnl_alpha_local": float(sum(x["oracle_ev_alpha"] for x in mine)),
                }
            )
            settled.append({"round": r, "revealed": revealed, "value": v_true})
            post.settle(v_true)
    except _Stop:
        pass

    ok = status == "ok"

    def total(key: str) -> float | None:
        return float(sum(x[key] for x in steps)) if ok else None

    return _jsonable(
        {
            "trace_version": TRACE_VERSION,
            "agent": getattr(agent, "name", type(agent).__name__),
            "provenance": provenance(agent),
            "session": session.to_dict(),
            "seed": int(seed),
            "status": status,
            "error": error,
            "pnl": float(sum(x["pnl"] for x in rounds)) if ok else None,
            "xpnl": total("ev"),
            "xpnl_alpha": total("ev_alpha"),
            "bayes_xpnl_local": total("bayes_ev"),
            "bayes_xpnl_alpha_local": total("bayes_ev_alpha"),
            "oracle_xpnl_alpha_local": total("oracle_ev_alpha"),
            "rounds": rounds,
            "steps": steps,
        }
    )


def trace_key(trace: dict[str, Any]) -> tuple[str, int]:
    return trace["session"]["id"], int(trace["seed"])
