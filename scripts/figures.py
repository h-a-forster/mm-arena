"""Build the README figures from a run directory.

    uv run python scripts/figures.py results/core-v1 docs/figures

Writes leaderboard, spread (edge vs quote width), variance (realized vs expected P&L) and one
example episode per LLM agent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from mmarena.metrics import load_episodes
from mmarena.plots import (
    GRID,
    INK,
    INK_2,
    MUTED,
    SERIES_1,
    SERIES_2,
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


def main(run_dir: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_report(run_dir, write=False)
    save(plot_leaderboard(report), out / "leaderboard")
    plot_spread(report, out / "spread")
    traces = load_run(run_dir)
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
        save(plot_episode(worst), out / f"episode-{tag}")
    print(f"wrote figures to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    np.seterr(all="ignore")
    main(sys.argv[1], sys.argv[2])
