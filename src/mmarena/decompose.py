"""Centring vs width: how much of an agent's shortfall comes from where it centres its quotes
and how much from how wide it quotes.

Each ``ok`` trace is replayed along the agent's own path (the same public posterior the engine
used). On steps where the agent quoted both sides and a Bayes quote exists ("covered" steps),
three counterfactual quotes are priced with the exact one-step expectation:

- agent mid, Bayes width: the agent's centre with the Bayes half-spread;
- Bayes mid, agent width: the Bayes quote's centre with the agent's half-spread;
- posterior mean, agent width: the public posterior mean with the agent's half-spread.

Uncovered steps (one-sided quotes, inventory-limit steps, invalid replies) keep their as-played
value in every column. Totals are in prior-sd units and shown as a share of the Bayes quoter's
expected P&L on the same steps, so the as-played column equals 100 x local efficiency.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from mmarena.engine import _to_tick
from mmarena.games import Game, Market, make_game
from mmarena.market import Posterior, quote_value
from mmarena.metrics import select_ok

REL_TOL = 1e-6
COLUMNS = ("as_played", "agent_mid_bayes_width", "bayes_mid_agent_width", "mu_agent_width")


@dataclass
class TraceDecomposition:
    """Additive totals of one replayed trace, in prior-sd units."""

    as_played: float = 0.0
    agent_mid_bayes_width: float = 0.0
    bayes_mid_agent_width: float = 0.0
    mu_agent_width: float = 0.0
    bayes: float = 0.0
    steps: int = 0
    covered: int = 0
    mismatches: int = 0


def build_game(g: Mapping[str, Any]) -> Game:
    """Rebuild a trace's game from its spec, with the recorded market; checks the game id."""
    game = make_game(g["family"], int(g["seed"]), g["variant"], Market(**g["market"]))
    if game.id != g["id"]:
        raise ValueError(f"cannot rebuild game {g['id']} from its spec; got {game.id}")
    return game


def _agrees(a: float, b: float) -> bool:
    return abs(a - b) <= REL_TOL * max(abs(a), abs(b)) + 1e-12


def _snapped(centre: float, half: float, tick: float) -> tuple[float, float]:
    return _to_tick(centre - half, tick, up=False), _to_tick(centre + half, tick, up=True)


def _value(game: Game, w: np.ndarray, mu: float, bid: float | None, ask: float | None) -> float:
    return quote_value(game.levels, w, mu, bid, ask, game.market).ev


def decompose_trace(game: Game, trace: Mapping[str, Any]) -> TraceDecomposition:
    """Replay one ``ok`` trace on ``game`` and price the counterfactual quotes."""
    out = TraceDecomposition()
    s0 = game.prior_std or 1.0
    tick = game.market.tick
    post = Posterior(game)
    revealed = trace.get("revealed") or []
    prev_stage = None
    for s in trace["steps"]:
        stage = int(s["stage"])
        if prev_stage is not None and stage != prev_stage:
            for r in revealed:
                if int(r["stage"]) == stage:
                    post.reveal(int(r["component"]), float(r["value"]))
        prev_stage = stage
        w, mu = post.level_weights(), post.mean()
        bid, ask = s["bid"], s["ask"]
        bb, ba = s["bayes_bid"], s["bayes_ask"]

        ev = _value(game, w, mu, bid, ask)
        if not _agrees(ev, float(s["ev"])):
            out.mismatches += 1
        played = float(s["ev"])
        cf = [played, played, played]
        if None not in (bid, ask, bb, ba):
            out.covered += 1
            mid, half = 0.5 * (bid + ask), 0.5 * (ask - bid)
            bmid, bhalf = 0.5 * (bb + ba), 0.5 * (ba - bb)
            cf = [
                _value(game, w, mu, *_snapped(mid, bhalf, tick)),
                _value(game, w, mu, *_snapped(bmid, half, tick)),
                _value(game, w, mu, *_snapped(mu, half, tick)),
            ]
        out.as_played += played / s0
        out.agent_mid_bayes_width += cf[0] / s0
        out.bayes_mid_agent_width += cf[1] / s0
        out.mu_agent_width += cf[2] / s0
        out.bayes += float(s["bayes_ev"]) / s0
        out.steps += 1
        post.observe_trade(s["action"], bid, ask)
    return out


def _share(x: float, den: float) -> float:
    return 100.0 * x / den if den else math.nan


def decompose_runs(
    traces_by_agent: Mapping[str, Sequence[Mapping[str, Any]]],
    z_stats: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Centring-vs-width summary per agent.

    Games are rebuilt one at a time (some are large) and dropped once every agent's traces on
    them are replayed. ``z_stats[agent]`` supplies ``mid_bias_z``, ``mid_abs_z``, ``width_sd``
    and ``bayes_width_sd`` (from :func:`mmarena.metrics.aggregate`) for the descriptive columns.
    """
    chosen = {a: select_ok(ts)[0] for a, ts in traces_by_agent.items()}
    by_game: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for agent, ts in chosen.items():
        for t in ts:
            by_game.setdefault(str(t["game"]["id"]), []).append((agent, t))
    tot = {a: TraceDecomposition() for a in chosen}
    skipped = dict.fromkeys(chosen, 0)
    for items in by_game.values():
        try:
            game = build_game(items[0][1]["game"])
        except (ValueError, KeyError, TypeError):
            for agent, _ in items:
                skipped[agent] += 1
            continue
        for agent, t in items:
            d, a = decompose_trace(game, t), tot[agent]
            for f in ("as_played", "bayes", "steps", "covered", "mismatches"):
                setattr(a, f, getattr(a, f) + getattr(d, f))
            for f in COLUMNS[1:]:
                setattr(a, f, getattr(a, f) + getattr(d, f))
        del game
    out: dict[str, dict[str, Any]] = {}
    for agent, d in tot.items():
        z = (z_stats or {}).get(agent, {})
        bw = z.get("bayes_width_sd", math.nan)
        out[agent] = {
            "as_played": _share(d.as_played, d.bayes),
            "agent_mid_bayes_width": _share(d.agent_mid_bayes_width, d.bayes),
            "bayes_mid_agent_width": _share(d.bayes_mid_agent_width, d.bayes),
            "mu_agent_width": _share(d.mu_agent_width, d.bayes),
            "covered_share": _share(d.covered, d.steps),
            "mid_bias_z": z.get("mid_bias_z", math.nan),
            "mid_abs_z": z.get("mid_abs_z", math.nan),
            "width_ratio": z.get("width_sd", math.nan) / bw if bw else math.nan,
            "steps": d.steps,
            "covered_steps": d.covered,
            "mismatches": d.mismatches,
            "unreplayed_episodes": skipped[agent],
        }
    return out
