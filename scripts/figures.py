"""Build the README figures from a run directory.

    uv run python scripts/figures.py results/core-v1 docs/figures

Writes leaderboard, spread (edge vs quote width), cost (edge vs list price and latency, with the
Pareto frontier), variance (realized vs expected P&L) and one example episode per LLM agent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from mmarena.metrics import load_episodes
from mmarena.plots import (
    DPI,
    GRID,
    INK,
    INK_2,
    MUTED,
    SERIES_1,
    SERIES_2,
    SURFACE,
    _figure,
    _title,
    plot_episode,
    plot_leaderboard,
    plot_variance,
    save,
)
from mmarena.report import build_report, load_run

BASELINES = {"bayes", "bayes-noflow", "glosten-milgrom", "static", "random"}
# Label placement for the spread chart: (dx, dy in points, horizontal alignment).
LABEL_OFFSETS = {
    "opus 5.5@high": (-8, 4, "right"),
    "opus 5.5@low": (-8, 4, "right"),
    "fable 5.1@low": (8, -12, "left"),
    "haiku 5.5@high": (8, -16, "left"),
    "sonnet 5.5@high": (-8, 4, "right"),
    "bayes-noflow": (7, 2, "left"),
    "glosten-milgrom": (0, -14, "center"),
    "haiku 5.5@low": (8, -12, "left"),
}


def short(name: str) -> str:
    return name.replace("claude-cli:claude-", "").replace("-5-5", " 5.5").replace("-5-1", " 5.1")


def plot_spread(report, path: Path) -> None:
    """Edge captured against quote width relative to the Bayes quote, one point per agent."""
    fig, (ax,) = _figure(7.5, 4.6)
    for row in report.leaderboard:
        name = row["agent"]
        ratio = row["width_sd"] / row["bayes_width_sd"]
        edge = row["edge_captured"]
        llm = name not in BASELINES
        ax.scatter(
            ratio,
            edge,
            s=70 if llm else 45,
            color=SERIES_1 if llm else MUTED,
            zorder=3,
            edgecolor="white",
            linewidth=0.8,
        )
        dx, dy, ha = LABEL_OFFSETS.get(short(name), (7, 4, "left"))
        ax.annotate(
            short(name),
            (ratio, edge),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=9,
            color=INK if llm else INK_2,
            ha=ha,
        )
    ax.axhline(0, color=INK_2, linewidth=0.8)
    ax.axvline(1, color=SERIES_2, linewidth=1, linestyle="--")
    ax.text(1.0, ax.get_ylim()[0], " Bayes width", color=SERIES_2, fontsize=8.5, va="bottom")
    ax.set_xlabel("quote width / Bayes quote width (same states)")
    ax.set_ylabel("edge captured, % of Bayes")
    ax.grid(True, color=GRID, linewidth=0.6)
    _title(
        fig,
        "Edge tracks quote width",
        "LLMs centre their quotes well; the shortfall is spreads narrower than optimal",
    )
    save(fig, path)


MODEL_COLORS = {"haiku": "#3a9e6f", "sonnet": "#7a5cc7", "opus": SERIES_1, "fable": SERIES_2}
# Label placement for the cost chart, per panel: (dx, dy in points, horizontal alignment).
COST_OFFSETS = {
    "usd_1k": {},
    "sec": {"opus low": (6, 7, "left"), "fable low": (7, -14, "left")},
}


def llm_costs(report, traces) -> list[dict]:
    """Per LLM setup: edge captured, list-price USD per 1,000 quotes, mean seconds per quote."""
    rows = []
    for row in report.leaderboard:
        name = row["agent"]
        if name in BASELINES:
            continue
        steps = [s for t in traces[name] if t["status"] == "ok" for s in t["steps"]]
        lat = [(s.get("info") or {}).get("provider_latency_s") for s in steps]
        lat = [x for x in lat if isinstance(x, (int, float))]
        model, _, effort = short(name).partition("@")
        rows.append(
            {
                "name": name,
                "model": model.split()[0],
                "effort": effort,
                "edge": row["edge_captured"],
                "usd_1k": 1000 * row["cost_usd"] / len(steps),
                "sec": float(np.mean(lat)) if lat else float("nan"),
            }
        )
    return rows


def pareto(rows: list[dict], key: str) -> list[dict]:
    """Setups that no other setup beats on both edge and ``key`` (lower is better)."""
    out, best = [], -np.inf
    for r in sorted(rows, key=lambda r: (r[key], -r["edge"])):
        if r["edge"] > best:
            out.append(r)
            best = r["edge"]
    return out


def plot_cost(rows: list[dict], static_edge: float, path: Path) -> None:
    """Edge captured against list price and against latency, with the Pareto frontier."""
    fig, axes = _figure(11, 4.8, ncols=2)
    panels = (
        ("usd_1k", "USD per 1,000 quotes at API list prices (log)"),
        ("sec", "seconds per quote (mean model latency)"),
    )
    for ax, (key, xlabel) in zip(axes, panels, strict=True):
        front = pareto(rows, key)
        xs = [r[key] for r in front]
        ys = [r["edge"] for r in front]
        ax.plot(xs, ys, drawstyle="steps-post", color=INK_2, linewidth=1, linestyle="--", zorder=2)
        for model, color in MODEL_COLORS.items():
            pts = sorted(
                (r for r in rows if r["model"] == model), key=lambda r: r["effort"] != "low"
            )
            if not pts:
                continue
            ax.plot([r[key] for r in pts], [r["edge"] for r in pts], color=color, alpha=0.5, lw=1.2)
            for r in pts:
                high = r["effort"] == "high"
                ax.scatter(
                    r[key],
                    r["edge"],
                    s=70,
                    color=color if high else SURFACE,
                    edgecolor=color,
                    linewidth=1.6,
                    zorder=3,
                )
                label = f"{model} {r['effort']}"
                dx, dy, ha = COST_OFFSETS[key].get(label, (7, 4, "left"))
                ax.annotate(
                    label,
                    (r[key], r["edge"]),
                    xytext=(dx, dy),
                    textcoords="offset points",
                    fontsize=8.5,
                    color=INK,
                    ha=ha,
                    weight="bold" if r in front else "normal",
                )
        for y, text in ((100, "bayes"), (static_edge, "static (no model)")):
            ax.axhline(y, color=MUTED, linewidth=0.8, linestyle=":")
            ax.text(
                0.01,
                y,
                text,
                transform=ax.get_yaxis_transform(),
                color=MUTED,
                fontsize=8,
                va="bottom",
            )
        ax.axhline(0, color=INK_2, linewidth=0.8)
        if key == "usd_1k":
            ax.set_xscale("log")
            ticks = [1, 3, 10, 30, 100]
            ax.set_xticks(ticks, [f"${t}" for t in ticks])
            ax.minorticks_off()
        ax.set_ylim(-8, 106)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("edge captured, % of Bayes")
    _title(
        fig,
        "What the edge costs",
        "Hollow: low effort, filled: high effort. Dashed: Pareto frontier (bold labels). "
        "Latency through claude -p.",
    )
    save(fig, path)


def main(run_dir: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_report(run_dir, write=False)
    save(plot_leaderboard(report), out / "leaderboard")
    plot_spread(report, out / "spread")
    traces = load_run(run_dir)
    costs = llm_costs(report, traces)
    if costs:
        static = next((r["edge_captured"] for r in report.leaderboard if r["agent"] == "static"), 0)
        plot_cost(costs, static, out / "cost")
        for r in sorted(costs, key=lambda r: r["usd_1k"]):
            print(
                f"{short(r['name']):18s} edge {r['edge']:6.1f}  ${r['usd_1k']:7.2f}/1k quotes  "
                f"{r['sec']:5.1f} s/quote"
            )
    agents = load_episodes(traces)
    llms = [r["agent"] for r in report.leaderboard if r["agent"] not in BASELINES]
    if len(llms) >= 2:
        # The two best LLM runs: close in skill, so the estimator choice matters most.
        a, b = llms[0], llms[1]
        fig = plot_variance(agents, a, b)
        fig.texts[0].set_text(f"Realized vs expected P&L: {short(a)} minus {short(b)}")
        save(fig, out / "variance")
    for name in llms:
        # The episode where the agent's expected P&L falls furthest below Bayes on its own path.
        eps = [t for t in traces[name] if t["status"] == "ok" and t["game"]["variant"] == "classic"]
        worst = min(eps, key=lambda t: (t["xpnl"] - t["bayes_xpnl_local"]) / t["game"]["prior_std"])
        tag = short(name).replace(" 5.5", "").replace(" 5.1", "").replace("@", "-")
        # PNG only: the README embeds the PNGs, and the SVGs would be untracked clutter.
        plot_episode(worst).savefig(out / f"episode-{tag}.png", dpi=DPI, facecolor=SURFACE)
    print(f"wrote figures to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    np.seterr(all="ignore")
    main(sys.argv[1], sys.argv[2])
