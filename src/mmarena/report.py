"""Build a report from a run directory: ``summary.json``, ``leaderboard.csv``, ``REPORT.md``."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

from mmarena.metrics import (
    AgentEpisodes,
    EpisodeMetrics,
    Key,
    aggregate,
    bayes_reference,
    group_aggregates,
    load_episodes,
)
from mmarena.pricing import PRICES_AS_OF
from mmarena.runner import read_traces
from mmarena.stats import (
    N_BOOT,
    bootstrap_mean,
    bootstrap_ratio,
    bootstrap_ratio_gap,
    holm,
    paired_difference,
    rank_probabilities,
    variance_reduction,
)

REF_AGENT = "bayes"
REPORT_FILES = ("summary.json", "leaderboard.csv", "REPORT.md")


@dataclass
class Report:
    run_dir: Path
    leaderboard: list[dict[str, Any]]
    groups: list[dict[str, Any]]
    variants: list[dict[str, Any]]
    pairwise: list[dict[str, Any]]
    variance: dict[str, Any]
    reference_generated: int
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def best(self) -> str | None:
        return self.leaderboard[0]["agent"] if self.leaderboard else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_dir": self.run_dir.as_posix(),
            "settings": self.settings,
            "reference_generated": self.reference_generated,
            "leaderboard": self.leaderboard,
            "groups": self.groups,
            "variants": self.variants,
            "pairwise": self.pairwise,
            "variance": self.variance,
        }


def load_run(run_dir: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Traces per agent from the ``*.jsonl`` files in ``run_dir``, keyed by the traces' agent name.

    Files are usually one per agent; traces are grouped by their own ``agent`` field (falling
    back to the file stem), so renamed or merged files still score correctly.
    """
    run_dir = Path(run_dir)
    files = sorted(run_dir.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"no *.jsonl trace files in {run_dir}")
    out: dict[str, list[dict[str, Any]]] = {}
    for p in files:
        for t in read_traces(p):
            out.setdefault(str(t.get("agent") or p.stem), []).append(t)
    return out


def _shared(
    a: Sequence[EpisodeMetrics],
    b: Sequence[EpisodeMetrics],
    ref: Mapping[Key, float] | None = None,
) -> tuple[list[EpisodeMetrics], list[EpisodeMetrics]]:
    """Episodes both agents played (and that have a reference, if ``ref`` is given)."""
    bk = {e.key: e for e in b}
    pairs = [(e, bk[e.key]) for e in a if e.key in bk and (ref is None or e.key in ref)]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def _edge_ci(
    eps: Sequence[EpisodeMetrics], ref: Mapping[Key, float], n_boot: int, seed: int
) -> dict[str, float]:
    eps = [e for e in eps if e.key in ref]
    est = bootstrap_ratio(
        [e.xpnl_sd for e in eps],
        [ref[e.key] for e in eps],
        [e.game_id for e in eps],
        100.0,
        n_boot,
        seed,
    )
    return {"edge_lo": est.lo, "edge_hi": est.hi, "edge_se": est.se}


def build_report(
    run_dir: str | Path,
    out_dir: str | Path | None = None,
    n_boot: int = N_BOOT,
    seed: int = 0,
    delta: float = 0.1,
    generate_reference: bool = True,
    write: bool = True,
) -> Report:
    """Score every agent in ``run_dir`` and write the report files (to ``out_dir`` or run_dir).

    ``delta`` is the per-episode difference in expected P&L (prior-sd units) used for the
    episodes-needed power calculation.
    """
    run_dir = Path(run_dir)
    traces = load_run(run_dir)
    ref, generated = bayes_reference(traces, REF_AGENT, generate_reference)
    agents = load_episodes(traces)

    board = []
    for name, ae in agents.items():
        row = {"agent": name, "n_error": ae.n_error, **aggregate(ae.episodes, ref)}
        row.update(_edge_ci(ae.episodes, ref, n_boot, seed))
        xm = bootstrap_mean(
            [e.xpnl_sd for e in ae.episodes], [e.game_id for e in ae.episodes], n_boot, seed
        )
        row["xpnl_sd_lo"], row["xpnl_sd_hi"] = xm.lo, xm.hi
        board.append(row)
    board.sort(key=lambda r: -r["edge_captured"] if math.isfinite(r["edge_captured"]) else 1e300)

    num = {
        n: _per_game([e for e in a.episodes if e.key in ref], lambda e: e.xpnl_sd)
        for n, a in agents.items()
    }
    den = {
        n: _per_game([e for e in a.episodes if e.key in ref], lambda e: ref[e.key])
        for n, a in agents.items()
    }
    ranks = rank_probabilities(num, den, n_boot, seed)
    for i, row in enumerate(board):
        row["rank"] = i + 1
        row["rank_probs"] = ranks[row["agent"]]
        row["p_rank1"] = ranks[row["agent"]][0]

    groups = []
    for name, ae in agents.items():
        for (fam, var), agg in group_aggregates(ae.episodes, ref).items():
            eps = [e for e in ae.episodes if e.family == fam and e.variant == var]
            groups.append(
                {"agent": name, "family": fam, "variant": var, **agg}
                | _edge_ci(eps, ref, n_boot, seed)
            )

    variants = _variant_table(agents, ref, n_boot, seed)
    pairwise = _pairwise(agents, ref, n_boot, seed)
    best = board[0]["agent"] if board else None
    variance = _variance(agents, best, delta)

    report = Report(
        run_dir=run_dir,
        leaderboard=board,
        groups=groups,
        variants=variants,
        pairwise=pairwise,
        variance=variance,
        reference_generated=generated,
        settings={"n_boot": n_boot, "seed": seed, "delta": delta, "reference": REF_AGENT},
    )
    if write:
        write_report(report, Path(out_dir) if out_dir else run_dir)
    return report


def _per_game(eps: Sequence[EpisodeMetrics], fn) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in eps:
        out[e.game_id] = out.get(e.game_id, 0.0) + fn(e)
    return out


def _variant_table(
    agents: Mapping[str, AgentEpisodes], ref: Mapping[Key, float], n_boot: int, seed: int
) -> list[dict[str, Any]]:
    rows = []
    for name, ae in agents.items():
        row: dict[str, Any] = {"agent": name}
        parts = {}
        for fam in sorted({e.family for e in ae.episodes}):
            eps = [e for e in ae.episodes if e.family == fam and e.key in ref]
            row[f"edge_{fam}"] = aggregate(eps, ref)["edge_captured"]
        for var in ("classic", "perturbed"):
            eps = [e for e in ae.episodes if e.variant == var and e.key in ref]
            parts[var] = (
                [e.xpnl_sd for e in eps],
                [ref[e.key] for e in eps],
                [e.game_id for e in eps],
            )
            row[f"edge_{var}"] = aggregate(eps, ref)["edge_captured"] if eps else math.nan
        if parts["classic"][0] and parts["perturbed"][0]:
            gap = bootstrap_ratio_gap(parts["classic"], parts["perturbed"], 100.0, n_boot, seed)
            row.update(gap=gap.value, gap_lo=gap.lo, gap_hi=gap.hi)
        else:
            row.update(gap=math.nan, gap_lo=math.nan, gap_hi=math.nan)
        rows.append(row)
    return rows


def _pairwise(
    agents: Mapping[str, AgentEpisodes], ref: Mapping[Key, float], n_boot: int, seed: int
) -> list[dict[str, Any]]:
    rows = []
    for a, b in combinations(agents, 2):
        ea, eb = _shared(agents[a].episodes, agents[b].episodes, ref)
        if not ea:
            continue
        res = paired_difference(
            [e.xpnl_sd for e in ea],
            [e.xpnl_sd for e in eb],
            [ref[e.key] for e in ea],
            [e.game_id for e in ea],
            100.0,
            n_boot,
            seed=seed,
        )
        rows.append({"a": a, "b": b, **res.to_dict()})
    for row, p in zip(rows, holm([r["p_value"] for r in rows]), strict=True):
        row["p_holm"] = p
    return rows


def _variance(agents: Mapping[str, AgentEpisodes], best: str | None, delta: float) -> dict:
    per_agent = {}
    for name, ae in agents.items():
        eps = ae.episodes
        per_agent[name] = variance_reduction(
            [e.pnl_sd for e in eps], [e.xpnl_sd for e in eps], [e.game_id for e in eps], delta
        )
    paired = {}
    if best is not None:
        for name, ae in agents.items():
            if name == best:
                continue
            ea, eb = _shared(agents[best].episodes, ae.episodes)
            if len(ea) < 2:
                continue
            paired[name] = variance_reduction(
                [x.pnl_sd - y.pnl_sd for x, y in zip(ea, eb, strict=True)],
                [x.xpnl_sd - y.xpnl_sd for x, y in zip(ea, eb, strict=True)],
                [x.game_id for x in ea],
                delta,
            )
    return {"delta": delta, "best": best, "per_agent": per_agent, "paired_vs_best": paired}


# --------------------------------------------------------------------------- writing


def _clean(x: Any) -> Any:
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, Mapping):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def _f(x: float | None, nd: int = 2, pct: bool = False) -> str:
    if x is None or not math.isfinite(x):
        return "-"
    return f"{100 * x:.{nd}f}" if pct else f"{x:.{nd}f}"


def _ci(v: float, lo: float, hi: float, nd: int = 1) -> str:
    if not math.isfinite(v):
        return "-"
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return _f(v, nd)
    return f"{v:.{nd}f} [{lo:.{nd}f}, {hi:.{nd}f}]"


def _p(p: float) -> str:
    if not math.isfinite(p):
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]], align: str = "") -> list[str]:
    align = align or "l" + "r" * (len(header) - 1)
    sep = ["---:" if c == "r" else "---" for c in align]
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


LEADERBOARD_COLUMNS = (
    "rank",
    "agent",
    "episodes",
    "games",
    "n_error",
    "edge_captured",
    "edge_lo",
    "edge_hi",
    "p_rank1",
    "xpnl_sd",
    "pnl_sd",
    "local_efficiency",
    "capture_sd",
    "adverse_sd",
    "pnl_informed_sd",
    "pnl_noise_sd",
    "mid_abs_z",
    "mid_bias_z",
    "mid_rmse_z",
    "width_sd",
    "bayes_width_sd",
    "beta_flow",
    "beta_reveal",
    "fill_response",
    "invalid_rate",
    "one_sided_rate",
    "no_quote_rate",
    "dominated_rate",
    "limit_step_rate",
    "abs_final_position",
    "tokens_per_episode",
    "cost_usd",
    "cost_usd_per_episode",
    "latency_s_per_step",
)


def write_report(report: Report, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(_clean(report.to_dict()), indent=2) + "\n", encoding="utf-8"
    )
    with (out_dir / "leaderboard.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(LEADERBOARD_COLUMNS)
        for row in report.leaderboard:
            vals = [row.get(c) for c in LEADERBOARD_COLUMNS]
            w.writerow(["" if isinstance(v, float) and not math.isfinite(v) else v for v in vals])
    (out_dir / "REPORT.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(r: Report) -> str:
    lines = [f"# mm-arena report: {r.run_dir.name}", ""]
    n_eps = max((row["episodes"] for row in r.leaderboard), default=0)
    n_games = max((row["games"] for row in r.leaderboard), default=0)
    lines += [
        f"{len(r.leaderboard)} agents, up to {n_eps} episodes on {n_games} games. "
        f"Reference: `{REF_AGENT}` (myopic Bayes-optimal quoter). "
        f"Intervals: 95% game-clustered bootstrap, {r.settings.get('n_boot')} draws.",
        "",
    ]
    if r.reference_generated:
        lines += [f"Reference episodes generated on the fly: {r.reference_generated}.", ""]
    errs = [f"`{row['agent']}` {row['n_error']}" for row in r.leaderboard if row["n_error"]]
    if errs:
        lines += ["Episodes excluded (status not ok): " + ", ".join(errs) + ".", ""]

    lines += ["## Leaderboard", ""]
    has_cost = any(math.isfinite(row["cost_usd"]) for row in r.leaderboard)
    header = [
        "#",
        "agent",
        "edge captured % [95% CI]",
        "P(best)",
        "xpnl/sd",
        "pnl/sd",
        "mid abs z",
        "beta flow",
        "beta reveal",
        "invalid %",
        "dominated %",
    ]
    if has_cost:
        header.append("USD/episode")
    rows = []
    for row in r.leaderboard:
        cells = [
            str(row["rank"]),
            f"`{row['agent']}`",
            _ci(row["edge_captured"], row["edge_lo"], row["edge_hi"]),
            _f(row["p_rank1"]),
            _f(row["xpnl_sd"], 3),
            _f(row["pnl_sd"], 3),
            _f(row["mid_abs_z"]),
            _f(row["beta_flow"]),
            _f(row["beta_reveal"]),
            _f(row["invalid_rate"], 1, pct=True),
            _f(row["dominated_rate"], 1, pct=True),
        ]
        if has_cost:
            cells.append(_f(row["cost_usd_per_episode"], 4))
        rows.append(cells)
    lines += _table(header, rows, "rl" + "r" * (len(header) - 2)) + [""]

    lines += ["## By family and variant", ""]
    fams = sorted({g["family"] for g in r.groups})
    header = ["agent", *fams, "classic", "perturbed", "classic - perturbed [95% CI]"]
    order = [row["agent"] for row in r.leaderboard]
    vt = {v["agent"]: v for v in r.variants}
    rows = []
    for a in order:
        v = vt[a]
        rows.append(
            [
                f"`{a}`",
                *[_f(v.get(f"edge_{f}", math.nan), 1) for f in fams],
                _f(v["edge_classic"], 1),
                _f(v["edge_perturbed"], 1),
                _ci(v["gap"], v["gap_lo"], v["gap_hi"]),
            ]
        )
    lines += _table(header, rows) + [""]
    lines += [
        "Edge captured %, per family and per variant. Classic games are textbook questions; "
        "perturbed games are drawn fresh per seed. A positive gap that excludes zero suggests "
        "recall of known answers.",
        "",
    ]

    best = r.best
    lines += [f"## Pairwise vs `{best}`", ""]
    rows = []
    for p in r.pairwise:
        if best not in (p["a"], p["b"]):
            continue
        sign = 1.0 if p["a"] == best else -1.0
        other = p["b"] if p["a"] == best else p["a"]
        d, lo, hi = (sign * p[k] for k in ("diff_value", "diff_lo", "diff_hi"))
        lo, hi = min(lo, hi), max(lo, hi)
        rows.append(
            [f"`{other}`", _ci(d, lo, hi), str(p["n_games"]), _p(p["p_value"]), _p(p["p_holm"])]
        )
    lines += _table(["agent", f"`{best}` minus agent, pp [95% CI]", "games", "p", "p (Holm)"], rows)
    lines += [
        "",
        "Difference in edge captured on shared episodes. p: game-level sign-flip permutation "
        "test. Holm correction across all agent pairs (see `summary.json`).",
        "",
    ]

    lines += ["## Variance: realized vs expected P&L", ""]
    var = r.variance
    rows = []
    for a in order:
        v = var["per_agent"].get(a)
        if not v:
            continue
        rows.append(
            [
                f"`{a}`",
                _f(v["se_pnl"], 3),
                _f(v["se_xpnl"], 3),
                _f(v["se_ratio"], 1),
                _f(v["episodes_needed_pnl"], 0),
                _f(v["episodes_needed_xpnl"], 0),
                _f(v["episodes_ratio"], 1),
            ]
        )
    lines += _table(
        ["agent", "SE pnl/sd", "SE xpnl/sd", "SE ratio", "n (pnl)", "n (xpnl)", "n ratio"], rows
    )
    lines += [""]
    paired = var["paired_vs_best"]
    if paired:
        rows = [
            [
                f"`{best}` - `{a}`",
                _f(v["sd_pnl"], 3),
                _f(v["sd_xpnl"], 3),
                _f(v["episodes_needed_pnl"], 0),
                _f(v["episodes_needed_xpnl"], 0),
                _f(v["episodes_ratio"], 1),
            ]
            for a, v in paired.items()
        ]
        lines += _table(
            ["paired difference", "SD pnl/sd", "SD xpnl/sd", "n (pnl)", "n (xpnl)", "n ratio"],
            rows,
        )
        lines += [""]
    lines += [
        f"SE: game-clustered standard error of the mean per-episode score. n: episodes needed "
        f"to detect a mean difference of {var['delta']:g} prior sd per episode at 80% power "
        f"(two-sided, alpha 0.05). Both scores have the same expectation; xpnl removes the "
        f"settlement and fill noise. A leaderboard on realized P&L needs n ratio times as "
        f"many episodes for the same power.",
        "",
    ]

    lines += ["## How to read the metrics", ""]
    lines += [f"- **{k}**: {v}" for k, v in METRIC_NOTES if k != "USD/episode" or has_cost]
    lines += [""]
    return "\n".join(lines)


METRIC_NOTES = (
    (
        "edge captured %",
        "100 x sum(agent xpnl) / sum(Bayes xpnl) over the same (game, seed) episodes, in prior-sd "
        "units. 100 = myopic Bayes-optimal, 0 = never quoting, below 0 = loses money in "
        "expectation. Above 100 is possible: the reference is myopic.",
    ),
    ("P(best)", "share of bootstrap draws in which the agent has the highest edge captured."),
    (
        "xpnl/sd",
        "mean expected P&L per episode in prior standard deviations: the sum of the exact "
        "one-step expected profit of each quote given the public posterior.",
    ),
    ("pnl/sd", "mean realized P&L per episode in prior standard deviations. Noisy."),
    (
        "mid abs z",
        "mean |mid - mu| / sd over two-sided quotes, where mu and sd are the public posterior "
        "mean and sd (sd floored at one tick). Measures belief error. Bayes is not 0: its "
        "optimal quote is not centered on mu when the posterior is skewed.",
    ),
    (
        "beta flow",
        "slope (through the origin) of the agent's mid change on the Bayes quote's mid change "
        "between consecutive steps in the same stage, where only order flow moves the "
        "posterior. 1 = updates like Bayes, 0 = ignores order flow, above 1 = overreacts.",
    ),
    ("beta reveal", "the same slope across stage boundaries, where public reveals arrive."),
    (
        "invalid %",
        "steps whose output could not be used (format, exception, non-finite, crossed).",
    ),
    (
        "dominated %",
        "steps with a bid above the highest possible value or an ask below the lowest: a "
        "certain loss if filled.",
    ),
    (
        "USD/episode",
        f"API list price of the tokens used (`mmarena.pricing`, prices as of {PRICES_AS_OF}); "
        "the provider's reported cost for models without a listed price.",
    ),
    (
        "summary.json",
        "also holds local efficiency, capture and adverse selection, realized P&L by taker type, "
        "mid bias and RMSE, width vs Bayes width, fill response, one-sided and no-quote rates, "
        "inventory-limit steps, final position, tokens, cost and latency, per agent and per "
        "(family, variant).",
    ),
)
