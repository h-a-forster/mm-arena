"""Figures for traces and reports. Needs matplotlib (``pip install mm-arena[plot]``).

Every function returns a matplotlib ``Figure``; pass ``path`` (without extension) to save it as
PNG and SVG. Figures use the object API and never touch pyplot state.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from mmarena.stats import episodes_needed

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from mmarena.metrics import AgentEpisodes
    from mmarena.report import Report

DPI = 160

# Light theme. Categorical slots 1-2 of the reference palette (validated for CVD separation).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES_1 = "#2a78d6"  # agent / expected P&L
SERIES_2 = "#eb6834"  # Bayes reference / realized P&L
BAND = "#e8e7e2"
DIVERGING = ("#a32d2d", "#e34948", "#f0efec", "#3987e5", "#184f95")


def _require_matplotlib():
    try:
        import matplotlib  # noqa: F401
        from matplotlib.figure import Figure
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "plotting needs matplotlib: pip install 'mm-arena[plot]' (or pip install matplotlib)"
        ) from exc
    return Figure


def _figure(w: float, h: float, ncols: int = 1):
    Figure = _require_matplotlib()
    fig = Figure(figsize=(w, h), facecolor=SURFACE, layout="constrained")
    axes = fig.subplots(1, ncols, squeeze=False)[0]
    for ax in axes:
        _style(ax)
    return fig, axes


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelcolor=INK_2, labelsize=8, length=3, width=0.8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(INK_2)
    ax.yaxis.label.set_color(INK_2)
    ax.xaxis.label.set_size(9)
    ax.yaxis.label.set_size(9)


def _title(fig_or_ax, title: str, subtitle: str = "") -> None:
    if hasattr(fig_or_ax, "suptitle"):
        fig_or_ax.suptitle(title, x=0.01, ha="left", fontsize=11, color=INK, fontweight="bold")
    else:
        fig_or_ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
    if subtitle:
        ax = fig_or_ax.axes[0] if hasattr(fig_or_ax, "axes") else fig_or_ax
        ax.set_title(subtitle, loc="left", fontsize=8.5, color=INK_2, pad=6)


def _panel_title(ax, text: str) -> None:
    ax.set_title(text, loc="left", fontsize=9, color=INK, pad=6)


def save(fig: Figure, path: str | Path) -> list[Path]:
    """Write ``path.png`` (dpi 160) and ``path.svg``. Returns the written paths."""
    path = Path(path)
    if path.suffix in (".png", ".svg"):
        path = path.with_suffix("")
    path.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for ext in ("png", "svg"):
        p = path.with_suffix(f".{ext}")
        fig.savefig(p, dpi=DPI, facecolor=SURFACE)
        out.append(p)
    return out


def _maybe_save(fig: Figure, path: str | Path | None) -> Figure:
    if path is not None:
        save(fig, path)
    return fig


# --------------------------------------------------------------------------- (a) one episode


def plot_episode(trace: Mapping[str, Any], path: str | Path | None = None) -> Figure:
    """Quotes, public posterior, Bayes quotes, fills and reveals for one episode."""
    steps = trace["steps"]
    g = trace["game"]
    n = len(steps)
    fig, (ax,) = _figure(8.0, 4.4)
    x = np.arange(n + 1)

    def held(key: str) -> np.ndarray:
        v = [np.nan if s[key] is None else s[key] for s in steps]
        return np.array([*v, v[-1]], dtype=float)

    mu, sd = held("mu"), held("sd")
    ax.fill_between(x, mu - sd, mu + sd, step="post", color=BAND, linewidth=0, label="±1 sd")
    ax.step(x, mu, where="post", color=INK_2, linewidth=1.2, label="posterior mean")
    ax.step(x, held("bid"), where="post", color=SERIES_1, linewidth=2)
    ax.step(x, held("ask"), where="post", color=SERIES_1, linewidth=2, label="agent quote")
    # Bayes on top, dashed, so it stays visible where the agent quotes the same prices.
    dash = {"color": SERIES_2, "linewidth": 1.6, "linestyle": (0, (4, 2)), "zorder": 3}
    ax.step(x, held("bayes_bid"), where="post", **dash)
    ax.step(x, held("bayes_ask"), where="post", label="Bayes quote", **dash)
    v = float(trace["value"])
    ax.axhline(v, color=INK, linewidth=1.0, label=f"settlement V = {v:g}")

    styles = {
        ("buy", "informed"): ("^", INK, "buy at ask, informed"),
        ("buy", "noise"): ("^", "none", "buy at ask, noise"),
        ("sell", "informed"): ("v", INK, "sell at bid, informed"),
        ("sell", "noise"): ("v", "none", "sell at bid, noise"),
    }
    for (action, taker), (marker, face, label) in styles.items():
        pts = [
            (s["t"] + 0.5, s["price"])
            for s in steps
            if s["action"] == action and s["taker"] == taker
        ]
        if pts:
            px, py = zip(*pts, strict=True)
            ax.scatter(
                px,
                py,
                marker=marker,
                s=46,
                facecolors=face,
                edgecolors=INK,
                linewidths=1.2,
                zorder=5,
                label=label,
            )

    q = g["market"]["quotes_per_stage"]
    by_stage: dict[int, list[str]] = {}
    for r in trace.get("revealed", []):
        by_stage.setdefault(r["stage"], []).append(f"{r['name']} = {r['value']:g}")
    for stage in range(1, math.ceil(n / q)):
        ax.axvline(stage * q, color=AXIS, linewidth=0.8)
        if stage in by_stage:
            ax.annotate(
                "\n".join(by_stage[stage]),
                xy=(stage * q, 1.0),
                xycoords=("data", "axes fraction"),
                xytext=(3, -3),
                textcoords="offset points",
                va="top",
                fontsize=7.5,
                color=INK_2,
            )
    ax.set_xlim(0, n)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + 0.12 * (hi - lo))  # room for reveal labels
    ax.set_xlabel("quote step")
    ax.set_ylabel("price")
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=8,
        labelcolor=INK_2,
    )
    xs, ps = trace.get("xpnl"), trace.get("pnl")
    sub = f"{g['title']} ({g['family']}, {g['variant']}), seed {trace['seed']}"
    sub += f", agent {trace['agent']}"
    if xs is not None and ps is not None:
        sub += f". xpnl {xs:.2f}, pnl {ps:.2f}"
    _title(fig, f"Episode {g['id']}", sub)
    return _maybe_save(fig, path)


# --------------------------------------------------------------------------- (b) leaderboard


def plot_leaderboard(report: Report, path: str | Path | None = None) -> Figure:
    """Edge captured with 95% intervals, one row per agent."""
    rows = [r for r in report.leaderboard if math.isfinite(r["edge_captured"])]
    fig, (ax,) = _figure(7.0, 0.5 * len(rows) + 1.3)
    y = np.arange(len(rows))[::-1]
    for yi, r in zip(y, rows, strict=True):
        lo, hi = r["edge_lo"], r["edge_hi"]
        if math.isfinite(lo) and math.isfinite(hi):
            ax.plot([lo, hi], [yi, yi], color=SERIES_1, linewidth=2, solid_capstyle="round")
        ax.scatter(
            [r["edge_captured"]],
            [yi],
            s=50,
            color=SERIES_1,
            edgecolors=SURFACE,
            linewidths=2,
            zorder=3,
        )
        right = hi if math.isfinite(hi) else r["edge_captured"]
        ax.annotate(
            f"{r['edge_captured']:.1f}",
            xy=(right, yi),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color=INK_2,
        )
    for ref in (0, 100):
        ax.axvline(ref, color=INK_2, linewidth=0.8)
    ax.set_yticks(y, [r["agent"] for r in rows])
    ax.tick_params(axis="y", length=0, labelsize=9, labelcolor=INK)
    ax.grid(False, axis="y")
    ax.set_xlabel("edge captured, % of Bayes expected P&L (95% game-clustered CI)")
    ax.margins(x=0.08)
    _title(fig, "Leaderboard", "100 = myopic Bayes-optimal quoter, 0 = never quoting")
    return _maybe_save(fig, path)


# --------------------------------------------------------------------------- (c) variance


def plot_variance(
    agents: Mapping[str, AgentEpisodes],
    a: str,
    b: str,
    delta: float = 0.1,
    path: str | Path | None = None,
) -> Figure:
    """Paired difference ``a - b``: running mean and standard error for pnl vs xpnl."""
    eb = {e.key: e for e in agents[b].episodes}
    pairs = [(e, eb[e.key]) for e in agents[a].episodes if e.key in eb]
    if len(pairs) < 2:
        raise ValueError(f"{a!r} and {b!r} share fewer than 2 episodes")
    dp = np.array([x.pnl_sd - y.pnl_sd for x, y in pairs])
    dx = np.array([x.xpnl_sd - y.xpnl_sd for x, y in pairs])
    k = np.arange(1, len(dp) + 1)
    fig, (ax1, ax2) = _figure(9.0, 3.8, ncols=2)

    ax1.plot(k, np.cumsum(dp) / k, color=SERIES_2, linewidth=2, label="realized pnl")
    ax1.plot(k, np.cumsum(dx) / k, color=SERIES_1, linewidth=2, label="expected pnl (xpnl)")
    ax1.axhline(0, color=INK_2, linewidth=0.8)
    ax1.set_xlabel("episodes")
    ax1.set_ylabel(f"running mean of {a} - {b}, prior sd")
    _panel_title(ax1, "Running mean of the paired difference")
    ax1.legend(frameon=False, fontsize=8, labelcolor=INK_2)

    sd_p, sd_x = float(np.std(dp, ddof=1)), float(np.std(dx, ddof=1))
    n_p, n_x = episodes_needed(sd_p, delta), episodes_needed(sd_x, delta)
    top = max(n_p, n_x, len(dp)) if math.isfinite(n_p) else len(dp)
    grid = np.unique(np.geomspace(1, top * 1.5, 200).astype(int))
    for sd, color, label, need in (
        (sd_p, SERIES_2, "realized pnl", n_p),
        (sd_x, SERIES_1, "expected pnl (xpnl)", n_x),
    ):
        ax2.plot(grid, sd / np.sqrt(grid), color=color, linewidth=2, label=label)
        if math.isfinite(need):
            se = sd / math.sqrt(need)
            ax2.scatter([need], [se], s=40, color=color, edgecolors=SURFACE, linewidths=2, zorder=3)
            ax2.annotate(
                f"n = {need:.0f}",
                xy=(need, se),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color=INK_2,
            )
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlabel("episodes (log)")
    ax2.set_ylabel("standard error, prior sd (log)")
    ratio = (sd_p / sd_x) ** 2 if sd_x > 0 else math.nan
    _panel_title(ax2, f"Episodes to detect {delta:g} sd at 80% power: {ratio:.1f}x with pnl")
    _title(fig, f"Realized vs expected P&L, paired difference {a} - {b}")
    return _maybe_save(fig, path)


# --------------------------------------------------------------------------- (d) heatmap


def plot_heatmap(report: Report, path: str | Path | None = None) -> Figure:
    """Edge captured per agent and (family, variant)."""
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

    agents = [r["agent"] for r in report.leaderboard]
    cols = sorted({(g["family"], g["variant"]) for g in report.groups})
    vals = np.full((len(agents), len(cols)), np.nan)
    for gr in report.groups:
        if gr["agent"] in agents:
            vals[agents.index(gr["agent"]), cols.index((gr["family"], gr["variant"]))] = gr[
                "edge_captured"
            ]
    fig, (ax,) = _figure(1.0 + 0.85 * len(cols), 0.5 * len(agents) + 1.8)
    ax.grid(False)
    finite = vals[np.isfinite(vals)]
    vmin = min(-100.0, float(finite.min())) if len(finite) else -100.0
    vmax = max(100.0, float(finite.max())) if len(finite) else 100.0
    cmap = LinearSegmentedColormap.from_list("mm_div", DIVERGING)
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax)
    im = ax.imshow(np.ma.masked_invalid(vals), cmap=cmap, norm=norm, aspect="auto")
    for i in range(len(agents)):
        for j in range(len(cols)):
            v = vals[i, j]
            if not np.isfinite(v):
                continue
            r, g, b, _ = cmap(norm(v))
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            ax.text(
                j,
                i,
                f"{v:.0f}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if lum < 0.5 else INK,
            )
    ax.set_xticks(range(len(cols)), [f"{f}\n{v}" for f, v in cols], fontsize=8)
    ax.set_yticks(range(len(agents)), agents, fontsize=9)
    ax.tick_params(length=0, labelcolor=INK_2)
    ax.tick_params(axis="y", labelcolor=INK)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(len(cols) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(agents) + 1) - 0.5, minor=True)
    ax.grid(True, which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, colors=MUTED, labelcolor=INK_2)
    cb.set_label("edge captured %", fontsize=8, color=INK_2)
    _title(fig, "Edge captured by family and variant", "100 = Bayes, 0 = no quoting")
    return _maybe_save(fig, path)


# --------------------------------------------------------------------------- all


def plot_run(
    run_dir: str | Path,
    out_dir: str | Path | None = None,
    report: Report | None = None,
    episode_trace: Mapping[str, Any] | None = None,
    pair: Sequence[str] | None = None,
) -> list[Path]:
    """Write the standard figures for a run directory. Returns the PNG paths."""
    from mmarena.metrics import load_episodes
    from mmarena.report import build_report, load_run

    _require_matplotlib()
    run_dir = Path(run_dir)
    out = Path(out_dir) if out_dir else run_dir / "plots"
    traces = load_run(run_dir)
    report = report or build_report(run_dir, write=False)
    agents = load_episodes(traces)
    paths = []
    for name, fig in (
        ("leaderboard", plot_leaderboard(report)),
        ("heatmap", plot_heatmap(report)),
    ):
        paths.append(save(fig, out / name)[0])
    names = [r["agent"] for r in report.leaderboard]
    if pair is None and len(names) >= 2:
        pair = names[:2]
    if pair is not None:
        fig = plot_variance(agents, pair[0], pair[1], report.settings.get("delta", 0.1))
        paths.append(save(fig, out / "variance")[0])
    if episode_trace is None and names:
        ok = [t for t in traces[names[0]] if t.get("status") == "ok"]
        episode_trace = max(ok, key=lambda t: len(t["steps"]), default=None)
    if episode_trace is not None:
        paths.append(save(plot_episode(episode_trace), out / "episode")[0])
    return paths
