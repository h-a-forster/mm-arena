"""Episode simulator.

One episode = one game instance, one hidden outcome, one market maker. Randomness (the hidden
outcome, who arrives each step and their private valuation shocks) is drawn up front from
``(game, episode seed)`` and never from the agent's behaviour. Every agent playing the same
``(game, seed)`` therefore faces the same dice and the same counterparties (common random
numbers), and score differences come from policy, not luck.
"""

from __future__ import annotations

import math
import time
import zlib
from typing import Any

import numpy as np

from mmarena import __version__
from mmarena.agents.base import Agent, AgentError, InfraError, Observation
from mmarena.games.base import Game
from mmarena.market import BUY, SELL, Posterior, optimal_quote, quote_value

# 2: adds ``provenance`` (package version, plus the agent's own record: provider, model,
#    options, harness version, step-0 prompt hash for LLM agents) and per-step
#    ``info.prompt_sha256`` for LLM agents.
TRACE_VERSION = 2


def provenance(agent: Agent) -> dict[str, Any]:
    """``{"mmarena": version, **agent.provenance()}``; the agent part is optional, best effort."""
    out: dict[str, Any] = {"mmarena": __version__}
    fn = getattr(agent, "provenance", None)
    if callable(fn):
        try:
            extra = fn()
        except Exception:  # noqa: BLE001 - provenance must never fail an episode
            extra = None
        if isinstance(extra, dict):
            out.update({k: v for k, v in extra.items() if k != "mmarena"})
    return out


def episode_rng(game: Game, seed: int) -> np.random.Generator:
    return np.random.default_rng([zlib.crc32(game.id.encode()), int(seed)])


def draw_episode(game: Game, seed: int) -> dict[str, Any]:
    """Pre-draw all exogenous randomness for an episode."""
    rng = episode_rng(game, seed)
    omega = int(rng.choice(len(game.prob), p=game.prob))
    n = game.n_steps
    return {
        "omega": omega,
        "u": rng.random(n),  # informed if u < alpha
        "z": rng.standard_normal(n),  # noise-trader valuation shock
        "e": rng.standard_normal(n),  # informed-trader signal noise
    }


def _to_tick(x: float, tick: float, up: bool) -> float:
    """Snap to the tick grid, widening: bids round down, asks round up."""
    units = round(x / tick, 6)  # absorb float noise such as 9.5 / 0.1 = 94.99999999999999
    if not math.isfinite(units):
        return math.nan
    return round((math.ceil(units) if up else math.floor(units)) * tick, 10)


def _clean_side(x: Any) -> float | None:
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return math.nan
    return x


def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def run_episode(game: Game, agent: Agent, seed: int) -> dict[str, Any]:
    """Play one episode and return its full trace (JSON-serialisable)."""
    draws = draw_episode(game, seed)
    omega = draws["omega"]
    v_true = float(game.value[omega])
    m = game.market
    post = Posterior(game)
    levels = game.levels
    revealed: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    position, cash = 0, 0.0
    status, error = "ok", None
    agent.reset(game)

    for t in range(game.n_steps):
        stage = game.stage_of(t)
        if t > 0 and stage != game.stage_of(t - 1):
            for c in game.reveals[stage - 1]:
                val = float(game.outcomes[omega, c])
                post.reveal(c, val)
                revealed.append(
                    {"stage": stage, "component": c, "name": game.components[c], "value": val}
                )
        bid_allowed = position < m.inventory_limit
        ask_allowed = position > -m.inventory_limit
        obs = Observation(
            game=game,
            step=t,
            stage=stage,
            revealed=tuple(dict(r) for r in revealed),
            history=tuple(dict(h) for h in history),
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
            q = agent.act(obs)
            info = dict(q.info)
            bid_q, ask_q = _clean_side(q.bid), _clean_side(q.ask)
        except InfraError as exc:
            status, error = "error", f"infra: {exc}"
            break
        except AgentError as exc:
            bid_q = ask_q = None
            invalid = "format"
            info = {"error": str(exc), **getattr(exc, "info", {})}
        except Exception as exc:  # noqa: BLE001 - an agent crash is the agent's fault
            bid_q = ask_q = None
            invalid = "exception"
            info = {"error": f"{type(exc).__name__}: {exc}"}
        latency = time.perf_counter() - started

        bid = None if bid_q is None else _to_tick(bid_q, m.tick, up=False)
        ask = None if ask_q is None else _to_tick(ask_q, m.tick, up=True)
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

        w = post.level_weights()
        mu, sd = post.mean(), post.std()
        support = levels[w > 0]
        qv = quote_value(levels, w, mu, bid, ask, m)
        b_bid, b_ask = optimal_quote(levels, w, mu, m, bid_allowed, ask_allowed)
        bayes = quote_value(levels, w, mu, b_bid, b_ask, m)

        informed = draws["u"][t] < m.alpha
        if informed:
            valuation = v_true + m.informed_noise * draws["e"][t]
        else:
            valuation = mu + m.noise_scale * draws["z"][t]
        action, price = None, None
        if ask is not None and valuation > ask:
            action, price = BUY, ask
            position -= 1
            cash += ask
        elif bid is not None and valuation < bid:
            action, price = SELL, bid
            position += 1
            cash -= bid
        post.observe_trade(action, bid, ask)

        history.append(
            {"step": t, "stage": stage, "bid": bid, "ask": ask, "action": action, "price": price}
        )
        steps.append(
            {
                "t": t,
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
                "p_buy": qv.p_buy,
                "p_sell": qv.p_sell,
                "ev": qv.ev,
                "capture": qv.capture,
                "adverse": qv.adverse,
                "bayes_bid": b_bid,
                "bayes_ask": b_ask,
                "bayes_ev": bayes.ev,
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

    pnl = cash + position * v_true
    return _jsonable(
        {
            "trace_version": TRACE_VERSION,
            "agent": getattr(agent, "name", type(agent).__name__),
            "provenance": provenance(agent),
            "game": game.to_dict(),
            "seed": int(seed),
            "status": status,
            "error": error,
            "hidden": {
                name: float(game.outcomes[omega, i]) for i, name in enumerate(game.components)
            },
            "value": v_true,
            "position": position,
            "pnl": pnl if status == "ok" else None,
            "xpnl": float(sum(s["ev"] for s in steps)) if status == "ok" else None,
            "bayes_xpnl_local": float(sum(s["bayes_ev"] for s in steps))
            if status == "ok"
            else None,
            "revealed": revealed,
            "steps": steps,
        }
    )
