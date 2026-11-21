"""README numbers, recomputed from the committed traces.

    uv run python scripts/readme_numbers.py [results/core-v1]

First rebuilds ``REPORT.md``, ``summary.json`` and ``leaderboard.csv`` from the traces, in the
given run directory or (without one) in every ``results/*/`` with a ``REPORT.md``, and exits
non-zero if they differ from the committed files (floats in ``summary.json`` to a relative
1e-9, so other platforms' last-digit rounding passes). Then prints the run-level test of Fable
against Opus (REPORT.md prints it too; the script exits non-zero if the two disagree), Opus
@high run 2 minus @medium (both on Claude Code 2.1.296), per-run token, cost and family figures,
prompt-token gaps to run 1, and the Haiku run 3 and 4 comparison.
Pooled cost and latency come from ``scripts/figures.py``.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from mmarena.metrics import _step_usage, bayes_reference, load_episodes
from mmarena.report import _diff_row, build_report, is_llm, load_run, split_replicate
from mmarena.stats import welch

FABLE, OPUS, HAIKU = (
    "claude-cli:claude-fable-5-1@high",
    "claude-cli:claude-opus-5-5@high",
    "claude-cli:claude-haiku-5-5@high",
)
FILES = ("REPORT.md", "summary.json", "leaderboard.csv")


def _differs(a: Any, b: Any, path: str = "") -> str | None:
    """Where two parsed JSON/CSV values first differ, or None; floats to a relative 1e-9."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return f"{path}: keys {sorted(a.keys() ^ b.keys())}"
        return next((d for k in a if (d := _differs(a[k], b[k], f"{path}.{k}"))), None)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        return next(
            (
                d
                for i, (x, y) in enumerate(zip(a, b, strict=True))
                if (d := _differs(x, y, f"{path}[{i}]"))
            ),
            None,
        )
    if isinstance(a, float) or isinstance(b, float):
        try:
            x, y = float(a), float(b)
        except (TypeError, ValueError):
            return f"{path}: {a!r} != {b!r}"
        return (
            None if math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12) else f"{path}: {a!r} != {b!r}"
        )
    return None if a == b else f"{path}: {a!r} != {b!r}"


def _num(cell: str) -> Any:
    try:
        return float(cell)
    except ValueError:
        return cell


def check_report(run_dir: str) -> list[str]:
    """Rebuild the report files from the traces; what differs from the committed ones."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        build_report(run_dir, out_dir=tmp)
        new, old = Path(tmp), Path(run_dir)
        text = {f: [(d / f).read_text(encoding="utf-8") for d in (new, old)] for f in FILES}
        if len(set(text["REPORT.md"])) > 1:
            problems.append("REPORT.md")
        a, b = (json.loads(t) for t in text["summary.json"])
        a.pop("run_dir"), b.pop("run_dir")
        if d := _differs(a, b):
            problems.append(f"summary.json{d}")
        # Every trace must replay to the engine's recorded step values.
        bad = {k: v["mismatches"] for k, v in a["decomposition"].items() if v["mismatches"]}
        if bad:
            problems.append(f"replay mismatches {bad}")
        rows = [[[_num(c) for c in r] for r in csv.reader(t.splitlines())] for t in text[FILES[2]]]
        if d := _differs(*rows):
            problems.append(f"leaderboard.csv{d}")
    return problems


def prompt_tokens(step: dict[str, Any]) -> int:
    u = step["info"]["usage"]
    return sum(u.get(k, 0) for k in ("input_tokens", "cache_read_tokens", "cache_write_tokens"))


def by_step(traces: list[dict[str, Any]]) -> dict[tuple[str, int, int], dict[str, Any]]:
    return {(t["game"]["id"], t["seed"], s["t"]): s for t in traces for s in t["steps"]}


def main(run_dir: str | None = None) -> None:
    dirs = (
        [run_dir] if run_dir else [p.parent.as_posix() for p in Path("results").glob("*/REPORT.md")]
    )
    for d in sorted(dirs):
        if problems := check_report(d):
            sys.exit(f"{d}: report files differ from a rebuild from the traces: {problems}")
        print(f"{d}: REPORT.md, summary.json and leaderboard.csv match a rebuild")
    run_dir = run_dir or "results/core-v1"
    print()
    traces = load_run(run_dir)
    ref, _ = bayes_reference(traces)
    runs = load_episodes(traces)

    def edge(name: str) -> float:
        eps = runs[name].episodes
        return 100 * sum(e.xpnl_sd for e in eps) / sum(ref[e.key] for e in eps)

    def run_edges(setup: str) -> list[float]:
        return [edge(n) for n in runs if split_replicate(n)[0] == setup]

    t, df, p = welch(run_edges(FABLE), run_edges(OPUS))
    print(f"Fable vs Opus @high, run means: Welch t {t:.2f}, df {df:.1f}, p {p:.3f}")
    cell = f"| {t:.2f} ({df:.1f}) | {p:.3f} |"
    report = Path(run_dir, "REPORT.md").read_text(encoding="utf-8")
    row = next(ln for ln in report.splitlines() if ln.startswith(f"| `{FABLE}` - `{OPUS}` |"))
    if not row.endswith(cell):
        sys.exit(f"REPORT.md disagrees with the traces: {row!r} should end with {cell!r}")

    medium = OPUS.replace("@high", "@medium")
    d = _diff_row(runs[f"{OPUS}#r2"].episodes, runs[medium].episodes, ref, 2000, 0)
    print(
        f"Opus @high run 2 minus @medium: {d['diff_value']:+.1f} "
        f"[{d['diff_lo']:.1f}, {d['diff_hi']:.1f}]\n"
    )

    print(
        "run | quotes | output/quote | p95 | max | >8192 | prompt median | aux | USD/1k | families"
    )
    for name in (n for n in traces if is_llm(n)):
        steps = [s for t in traces[name] for s in t["steps"]]
        out = np.array([s["info"]["usage"]["output_tokens"] for s in steps])
        aux = sum("aux_input_tokens" in s["info"]["usage"] for s in steps)
        usd = sum(_step_usage(s["info"], "1h")[1] or 0.0 for s in steps)
        fam: dict[str, list[float]] = {}
        for e in runs[name].episodes:
            pair = fam.setdefault(e.family, [0.0, 0.0])
            pair[0] += e.xpnl_sd
            pair[1] += ref[e.key]
        fams = " ".join(f"{k} {100 * n / d:.1f}" for k, (n, d) in sorted(fam.items()))
        median = statistics.median(prompt_tokens(s) for s in steps)
        print(
            f"{name.removeprefix('claude-cli:claude-')} | {len(steps)} | {out.mean():.0f} | "
            f"{np.percentile(out, 95):.0f} | {out.max()} | {(out > 8192).sum()} | {median:.0f} | "
            f"{aux} | {1000 * usd / len(steps):.2f} | {fams}"
        )

    print("\nmedian prompt tokens minus run 1, same step of the same episode:")
    for name in traces:
        base, n = split_replicate(name)
        if n >= 2 and is_llm(name):
            first, later = by_step(traces[base]), by_step(traces[name])
            gaps = [prompt_tokens(later[k]) - prompt_tokens(first[k]) for k in first]
            print(f"  {name.removeprefix('claude-cli:claude-')}: {statistics.median(gaps):+.0f}")

    r3, r4 = traces[f"{HAIKU}#r3"], traces[f"{HAIKU}#r4"]
    hashes = {(t["game"]["id"], t["seed"]): t["provenance"]["prompt_sha256"] for t in r3}
    same = sum(hashes[(t["game"]["id"], t["seed"])] == t["provenance"]["prompt_sha256"] for t in r4)
    a, b = by_step(r3), by_step(r4)
    gap = statistics.median(prompt_tokens(b[k]) - prompt_tokens(a[k]) for k in a)
    games: dict[str, float] = {}
    for sign, name in ((1, f"{HAIKU}#r4"), (-1, f"{HAIKU}#r3")):
        for e in runs[name].episodes:
            games[e.game_id] = games.get(e.game_id, 0.0) + sign * e.xpnl_sd
    print(
        f"\nHaiku run 4 vs run 3: step-0 prompt hash equal on {same} of {len(r4)} episodes, "
        f"median prompt-token gap {gap:+.0f}, run 4 higher on "
        f"{sum(v > 0 for v in games.values())} of {len(games)} games"
    )

    sizes = {t["game"]["id"]: t["game"]["n_outcomes"] for t in traces["bayes"]}
    print(
        f"outcomes per game: {min(sizes.values())} to {max(sizes.values())}, "
        f"median {statistics.median(sizes.values()):g}"
    )


if __name__ == "__main__":
    main(*sys.argv[1:])
