"""Per-episode and aggregate metrics computed from traces.

All money quantities are divided by the game's prior standard deviation (``sd units``) before
they are summed across episodes, so a game with values in the thousands does not outweigh a
coin game. The headline is *edge captured*: the agent's expected P&L as a percentage of the
myopic Bayes-optimal quoter's expected P&L on the same ``(game, seed)`` episodes.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields
from typing import Any

INVALID_KINDS = ("format", "exception", "nonfinite", "crossed")

Key = tuple[str, int]


def episode_key(trace: Mapping[str, Any]) -> Key:
    return (str(trace["game"]["id"]), int(trace["seed"]))


def select_ok(traces: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep the last ``ok`` trace per ``(game id, seed)``.

    Returns the kept traces (in first-seen order) and the number of episodes that have no
    ``ok`` trace at all (errored and never recovered).
    """
    ok: dict[Key, dict[str, Any]] = {}
    seen: list[Key] = []
    for t in traces:
        k = episode_key(t)
        if k not in seen:
            seen.append(k)
        if t.get("status") == "ok":
            ok[k] = dict(t)
    order = [k for k in seen if k in ok]
    return [ok[k] for k in order], len(seen) - len(order)


@dataclass
class EpisodeMetrics:
    """Additive per-episode totals. Ratios are formed after summing across episodes."""

    agent: str
    game_id: str
    family: str
    variant: str
    seed: int
    prior_std: float
    n_steps: int = 0
    xpnl: float = 0.0  # raw units
    pnl: float = 0.0  # raw units
    xpnl_sd: float = 0.0
    pnl_sd: float = 0.0
    bayes_local_sd: float = 0.0  # sum of bayes_ev on the agent's own path, sd units
    capture_sd: float = 0.0
    adverse_sd: float = 0.0
    pnl_informed_sd: float = 0.0
    pnl_noise_sd: float = 0.0
    n_fills: int = 0
    n_fills_informed: int = 0
    z_n: int = 0
    z_abs: float = 0.0
    z_sum: float = 0.0
    z_sq: float = 0.0
    width_n: int = 0
    width_sd: float = 0.0
    bayes_width_sd: float = 0.0
    flow_n: int = 0
    flow_xy: float = 0.0
    flow_xx: float = 0.0
    reveal_n: int = 0
    reveal_xy: float = 0.0
    reveal_xx: float = 0.0
    flow_mu_xy: float = 0.0
    flow_mu_xx: float = 0.0
    reveal_mu_xy: float = 0.0
    reveal_mu_xx: float = 0.0
    dir_n: int = 0
    dir_right: int = 0
    invalid: dict[str, int] = field(default_factory=lambda: dict.fromkeys(INVALID_KINDS, 0))
    one_sided: int = 0
    no_quote: int = 0
    dominated: int = 0
    limit_steps: int = 0
    abs_position: float = 0.0
    tokens: float = 0.0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    cost_steps: int = 0  # steps that reported tokens or cost

    @property
    def key(self) -> Key:
        return (self.game_id, self.seed)


def _mid(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None:
        return None
    return 0.5 * (bid + ask)


def _step_usage(info: Mapping[str, Any]) -> tuple[float | None, float | None]:
    """Tokens and USD cost reported by an agent for one step, if any."""
    tokens = info.get("tokens")
    usage = info.get("usage")
    if tokens is None and isinstance(usage, Mapping):
        if usage.get("total_tokens") is not None:
            tokens = usage["total_tokens"]
        else:
            parts = [
                usage.get(k)
                for k in ("input_tokens", "output_tokens", "prompt_tokens", "completion_tokens")
            ]
            parts = [p for p in parts if isinstance(p, (int, float))]
            tokens = sum(parts) if parts else None
    cost = info.get("cost_usd", info.get("cost"))
    tokens = float(tokens) if isinstance(tokens, (int, float)) else None
    cost = float(cost) if isinstance(cost, (int, float)) else None
    return tokens, cost


def episode_metrics(trace: Mapping[str, Any]) -> EpisodeMetrics:
    """Compute the additive metrics of one ``ok`` trace."""
    g = trace["game"]
    s0 = float(g["prior_std"]) or 1.0
    tick = float(g["market"].get("tick", 0.0)) or 0.0
    v = float(trace["value"])
    m = EpisodeMetrics(
        agent=str(trace["agent"]),
        game_id=str(g["id"]),
        family=str(g["family"]),
        variant=str(g["variant"]),
        seed=int(trace["seed"]),
        prior_std=s0,
    )
    steps = trace["steps"]
    m.n_steps = len(steps)
    m.xpnl = float(trace["xpnl"])
    m.pnl = float(trace["pnl"])
    m.xpnl_sd = m.xpnl / s0
    m.pnl_sd = m.pnl / s0
    m.bayes_local_sd = float(trace["bayes_xpnl_local"]) / s0
    m.abs_position = abs(float(trace["position"]))

    mids: list[float | None] = []
    for s in steps:
        bid, ask = s["bid"], s["ask"]
        m.capture_sd += s["capture"] / s0
        m.adverse_sd += s["adverse"] / s0
        if s["action"] is not None:
            gain = (s["price"] - v) if s["action"] == "buy" else (v - s["price"])
            m.n_fills += 1
            if s["taker"] == "informed":
                m.n_fills_informed += 1
                m.pnl_informed_sd += gain / s0
            else:
                m.pnl_noise_sd += gain / s0
        mid = _mid(bid, ask)
        mids.append(mid)
        sd = float(s["sd"])
        if mid is not None and sd > 0:
            z = (mid - s["mu"]) / max(sd, tick)
            m.z_n += 1
            m.z_abs += abs(z)
            m.z_sum += z
            m.z_sq += z * z
        if mid is not None and s["bayes_bid"] is not None and s["bayes_ask"] is not None:
            m.width_n += 1
            m.width_sd += (ask - bid) / s0
            m.bayes_width_sd += (s["bayes_ask"] - s["bayes_bid"]) / s0
        inv = s["invalid"]
        if inv is not None:
            m.invalid[inv] = m.invalid.get(inv, 0) + 1
        else:
            allowed = [s["bid_allowed"], s["ask_allowed"]]
            quoted = [
                s["bid_allowed"] and s["bid_quoted"] is not None,
                s["ask_allowed"] and s["ask_quoted"] is not None,
            ]
            if not any(quoted):
                m.no_quote += 1
            elif all(allowed) and not all(quoted):
                m.one_sided += 1
        if (bid is not None and bid > s["hi"]) or (ask is not None and ask < s["lo"]):
            m.dominated += 1
        if not (s["bid_allowed"] and s["ask_allowed"]):
            m.limit_steps += 1
        m.latency_s += float(s.get("latency_s") or 0.0)
        tokens, cost = _step_usage(s.get("info") or {})
        if tokens is not None or cost is not None:
            m.cost_steps += 1
            m.tokens += tokens or 0.0
            m.cost_usd += cost or 0.0

    bmids = [_mid(s["bayes_bid"], s["bayes_ask"]) for s in steps]
    for a, b, ma, mb, ba, bb in zip(
        steps, steps[1:], mids, mids[1:], bmids, bmids[1:], strict=False
    ):
        if ma is None or mb is None:
            continue
        dm = (mb - ma) / s0
        dmu = (b["mu"] - a["mu"]) / s0
        dbm = (bb - ba) / s0 if ba is not None and bb is not None else None
        if b["stage"] == a["stage"]:
            m.flow_mu_xy += dm * dmu
            m.flow_mu_xx += dmu * dmu
            if dbm is not None:
                m.flow_n += 1
                m.flow_xy += dm * dbm
                m.flow_xx += dbm * dbm
            if a["action"] is not None:
                m.dir_n += 1
                up = a["action"] == "buy"
                m.dir_right += int(mb > ma if up else mb < ma)
        else:
            m.reveal_mu_xy += dm * dmu
            m.reveal_mu_xx += dmu * dmu
            if dbm is not None:
                m.reveal_n += 1
                m.reveal_xy += dm * dbm
                m.reveal_xx += dbm * dbm
    return m


def _div(a: float, b: float) -> float:
    return a / b if b else math.nan


def aggregate(
    episodes: Sequence[EpisodeMetrics], reference: Mapping[Key, float] | None = None
) -> dict[str, Any]:
    """Pool episodes into one row of metrics. ``reference`` maps key -> Bayes xpnl (sd units)."""
    n = len(episodes)
    tot: dict[str, float] = {}
    for f in fields(EpisodeMetrics):
        if f.type in ("int", "float") and f.name not in ("seed", "prior_std"):
            tot[f.name] = float(sum(getattr(e, f.name) for e in episodes))
    invalid = {k: sum(e.invalid.get(k, 0) for e in episodes) for k in INVALID_KINDS}
    steps = tot["n_steps"]
    ref = reference or {}
    with_ref = [e for e in episodes if e.key in ref]
    num = sum(e.xpnl_sd for e in with_ref)
    den = sum(ref[e.key] for e in with_ref)
    games = {e.game_id for e in episodes}
    return {
        "episodes": n,
        "games": len(games),
        "steps": int(steps),
        "edge_captured": 100.0 * _div(num, den),
        "edge_episodes": len(with_ref),
        "xpnl_sd": _div(tot["xpnl_sd"], n),
        "pnl_sd": _div(tot["pnl_sd"], n),
        "bayes_xpnl_sd": _div(den, len(with_ref)),
        "local_efficiency": _div(tot["xpnl_sd"], tot["bayes_local_sd"]),
        "capture_sd": _div(tot["capture_sd"], n),
        "adverse_sd": _div(tot["adverse_sd"], n),
        "pnl_informed_sd": _div(tot["pnl_informed_sd"], n),
        "pnl_noise_sd": _div(tot["pnl_noise_sd"], n),
        "fills_per_episode": _div(tot["n_fills"], n),
        "informed_fill_share": _div(tot["n_fills_informed"], tot["n_fills"]),
        "mid_abs_z": _div(tot["z_abs"], tot["z_n"]),
        "mid_bias_z": _div(tot["z_sum"], tot["z_n"]),
        "mid_rmse_z": math.sqrt(_div(tot["z_sq"], tot["z_n"])) if tot["z_n"] else math.nan,
        "width_sd": _div(tot["width_sd"], tot["width_n"]),
        "bayes_width_sd": _div(tot["bayes_width_sd"], tot["width_n"]),
        "beta_flow": _div(tot["flow_xy"], tot["flow_xx"]),
        "beta_reveal": _div(tot["reveal_xy"], tot["reveal_xx"]),
        "beta_flow_mu": _div(tot["flow_mu_xy"], tot["flow_mu_xx"]),
        "beta_reveal_mu": _div(tot["reveal_mu_xy"], tot["reveal_mu_xx"]),
        "fill_response": _div(tot["dir_right"], tot["dir_n"]),
        "invalid_rate": _div(sum(invalid.values()), steps),
        "invalid_by_kind": {k: _div(c, steps) for k, c in invalid.items()},
        "one_sided_rate": _div(tot["one_sided"], steps),
        "no_quote_rate": _div(tot["no_quote"], steps),
        "dominated_rate": _div(tot["dominated"], steps),
        "limit_step_rate": _div(tot["limit_steps"], steps),
        "abs_final_position": _div(tot["abs_position"], n),
        "tokens_per_episode": _div(tot["tokens"], n) if tot["cost_steps"] else math.nan,
        "cost_usd": tot["cost_usd"] if tot["cost_steps"] else math.nan,
        "cost_usd_per_episode": _div(tot["cost_usd"], n) if tot["cost_steps"] else math.nan,
        "latency_s_per_step": _div(tot["latency_s"], steps),
    }


def bayes_reference(
    traces_by_agent: Mapping[str, Sequence[Mapping[str, Any]]],
    ref_agent: str = "bayes",
    generate: bool = True,
) -> tuple[dict[Key, float], int]:
    """Bayes xpnl (sd units) per ``(game id, seed)`` for every episode any agent played.

    Taken from ``ref_agent``'s traces where present; otherwise the reference agent is replayed
    on the same ``(game, seed)`` (common random numbers make this exact). Returns the map and
    the number of episodes generated.
    """
    ref: dict[Key, float] = {}
    if ref_agent in traces_by_agent:
        for t in select_ok(traces_by_agent[ref_agent])[0]:
            ref[episode_key(t)] = float(t["xpnl"]) / (float(t["game"]["prior_std"]) or 1.0)
    missing: dict[Key, Mapping[str, Any]] = {}
    for traces in traces_by_agent.values():
        for t in traces:
            if t.get("status") == "ok" and episode_key(t) not in ref:
                missing.setdefault(episode_key(t), t["game"])
    if not missing or not generate:
        return ref, 0
    from mmarena.agents.baselines import BASELINES
    from mmarena.engine import run_episode
    from mmarena.games import make_game

    made = 0
    for (gid, seed), g in missing.items():
        game = make_game(g["family"], int(g["seed"]), g["variant"])
        if game.id != gid:
            raise ValueError(
                f"cannot rebuild game {gid} from (family, seed, variant); got {game.id}. "
                f"Run the {ref_agent!r} agent on this suite to provide reference traces."
            )
        t = run_episode(game, BASELINES[ref_agent](), seed)
        ref[(gid, seed)] = float(t["xpnl"]) / (game.prior_std or 1.0)
        made += 1
    return ref, made


@dataclass
class AgentEpisodes:
    agent: str
    episodes: list[EpisodeMetrics]
    n_error: int


def load_episodes(
    traces_by_agent: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, AgentEpisodes]:
    out = {}
    for agent, traces in traces_by_agent.items():
        ok, n_err = select_ok(traces)
        out[agent] = AgentEpisodes(agent, [episode_metrics(t) for t in ok], n_err)
    return out


def group_aggregates(
    episodes: Sequence[EpisodeMetrics], reference: Mapping[Key, float]
) -> dict[tuple[str, str], dict[str, Any]]:
    """Aggregate per ``(family, variant)``."""
    groups: dict[tuple[str, str], list[EpisodeMetrics]] = {}
    for e in episodes:
        groups.setdefault((e.family, e.variant), []).append(e)
    return {k: aggregate(v, reference) for k, v in sorted(groups.items())}
