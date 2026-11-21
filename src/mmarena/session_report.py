"""Report for a run directory of session traces (trace version 3, suite format 2).

    mm-arena report runs/core-v2

Writes ``summary.json``, ``leaderboard.csv`` and ``REPORT.md``. The score is the share of the
known-regime oracle's expected profit: ``100 * sum(ev_alpha) / sum(oracle ev_alpha)`` over the
run's sessions, each session in its game's prior-sd units. 0 is never quoting; 100 is the
profit of a quoter who is told the informed share and quotes the myopic optimum for it.

The oracle cannot be reached by a quoter that has to learn the informed share, and the best
such quoter is not computable for these sessions. Every table therefore prints an estimated
ceiling (``CEILING``): an estimate of the optimum for a quoter that does not know the informed
share, with its bracket, never used as a denominator. For a tier whose ceiling is below
``SECOND_COLUMN_BELOW`` the tables add the share of the best public quoter run so far
(``REF_PUBLIC``, tag ``REF_TAG``), a provisional reading aid that is not the score and is not
used in any test.

The oracle, ``bayes`` and ``bayes-nolearn`` are deterministic given the session and seed; when
a run directory lacks their traces they are computed from the session specs in the traces.
"""

from __future__ import annotations

import csv
import io
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from mmarena.report import _ci, _clean, _f, _p, _table, is_llm, split_replicate
from mmarena.runner import read_traces
from mmarena.session_metrics import Key, SessionMetrics, select_ok, session_metrics
from mmarena.stats import holm, welch

REPORT_FILES = ("summary.json", "leaderboard.csv", "REPORT.md")
TIER_ORDER = ("open", "mixed", "tight")
ORACLE = "oracle"
# Estimated optimum for a quoter that does not know the informed share, in % of the oracle:
# (estimate, bracket low, bracket high), from ``scripts/headroom_v2.py`` on 150 sessions per tier
# (base seed 50000) and ``scripts/ceiling_v2.py``. Bracket: from below, the best public quoter
# run (lookahead, weight 2 / 4 / 8 on the open / mixed / tight tier); from above, the
# relaxation "best public profit in round 1, the oracle's afterwards". Estimate: the best
# lookahead plus the gap between the exact optimum and the best lookahead in the solved
# miniature at the same noise ratio (0.1, 0.7 and 1.7 points). Later versions may tighten it;
# it is never a denominator. See docs/methodology-v2.md, section 6.
CEILING_TAG = "ce-1"
CEILING = {"open": (92.0, 91.6, 97.0), "mixed": (90.0, 88.9, 94.8), "tight": (67.0, 65.7, 86.0)}
SECOND_COLUMN_BELOW = 85.0
REF_PUBLIC = "bayes-lookahead-w8"
REF_TAG = "ref-1"
REFERENCES = (ORACLE, "bayes", "bayes-nolearn")
N_BOOT = 2000
N_PERM = 10000
EXACT_MAX = 14


def is_session_run(run_dir: str | Path) -> bool:
    """True if the run directory holds version-3 (session) traces."""
    for path in sorted(Path(run_dir).glob("*.jsonl")):
        for t in read_traces(path):
            return int(t.get("trace_version", 1)) >= 3
    return False


def _load(
    run_dir: Path,
) -> tuple[dict[str, dict[Key, SessionMetrics]], dict[Key, Mapping[str, Any]], str]:
    traces = []
    for path in sorted(run_dir.glob("*.jsonl")):
        traces += read_traces(path)
    if not traces:
        raise FileNotFoundError(f"no traces in {run_dir}")
    if any(int(t.get("trace_version", 1)) < 3 for t in traces):
        raise ValueError(f"{run_dir} mixes session traces with core-v1 traces")
    suites = {t.get("suite") for t in traces}
    if len(suites) > 1:
        raise ValueError(f"{run_dir} mixes suites {sorted(map(str, suites))}")
    runs: dict[str, dict[Key, SessionMetrics]] = defaultdict(dict)
    sessions: dict[Key, Mapping[str, Any]] = {}
    for t in select_ok(traces):
        m = session_metrics(t)
        runs[m.agent][m.key] = m
        sessions[m.key] = t["session"]
    return dict(runs), sessions, str(next(iter(suites)))


def _computed(name: str, sessions: Mapping[Key, Mapping[str, Any]]) -> dict[Key, SessionMetrics]:
    """Run a deterministic reference baseline on every session (rebuilt from its spec)."""
    from mmarena.agents.session_baselines import SESSION_BASELINES
    from mmarena.session_engine import run_session
    from mmarena.sessions import session_from_dict

    out = {}
    for key, spec in sessions.items():
        trace = run_session(session_from_dict(spec), SESSION_BASELINES[name](), key[1])
        out[key] = session_metrics(trace)
    return out


def _tiers(sessions: Mapping[Key, Mapping[str, Any]]) -> list[str]:
    present = {s["tier"] for s in sessions.values()}
    return [t for t in TIER_ORDER if t in present] + sorted(present - set(TIER_ORDER))


class _Boot:
    """Shared stratified bootstrap: sessions resampled with replacement within each tier."""

    def __init__(self, keys_by_tier: Mapping[str, list[Key]], n_boot: int, seed: int) -> None:
        rng = np.random.default_rng(seed)
        self.keys = keys_by_tier
        self.counts = {
            t: rng.multinomial(len(ks), np.full(len(ks), 1 / len(ks)), size=n_boot)
            for t, ks in keys_by_tier.items()
        }

    def sums(self, values: Mapping[Key, float], tiers: Sequence[str]) -> np.ndarray:
        total = 0.0
        for t in tiers:
            v = np.array([values[k] for k in self.keys[t]])
            total = total + self.counts[t] @ v
        return np.asarray(total)


def _interval(value: float, draws: np.ndarray) -> dict[str, float]:
    draws = draws[np.isfinite(draws)]
    if not len(draws) or not math.isfinite(value):
        return {"value": value, "lo": math.nan, "hi": math.nan, "p_le0": math.nan}
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {"value": value, "lo": float(lo), "hi": float(hi), "p_le0": float(np.mean(draws <= 0))}


def learning_response(half: np.ndarray, bayes: np.ndarray, prior: np.ndarray) -> float:
    """Coefficient on the Bayes half-width when the agent's half-width is regressed on the Bayes
    and the prior-regime half-widths together (with intercept).

    1 for a quoter whose width follows the Bayes quote, 0 for one whose width follows the
    prior-regime quote or neither. NaN when the two reference widths do not vary separately.
    """
    if len(half) < 4:
        return math.nan
    design = np.column_stack([np.ones(len(half)), bayes, prior])
    beta, _, rank, _ = np.linalg.lstsq(design, half, rcond=None)
    if rank < 3:
        return math.nan
    # A width that is exactly linear in the prior-regime width gives 0 up to rounding, whose
    # sign varies by machine; real coefficients are far above this (none below 1e-7 seen).
    return 0.0 if abs(beta[1]) < 1e-9 else float(beta[1])


def _one_sided_flip(d: Sequence[float], n_perm: int = N_PERM, seed: int = 0) -> float:
    """One-sided sign-flip p-value for ``sum(d) > 0`` (``d``: per-session differences)."""
    d = np.asarray(d, dtype=float)
    if not len(d):
        return math.nan
    obs = d.sum()
    tol = 1e-12 * max(1.0, float(np.abs(d).sum()))
    if len(d) <= EXACT_MAX:
        signs = np.array(list(product((1.0, -1.0), repeat=len(d))))
        return float(np.mean(signs @ d >= obs - tol))
    signs = np.random.default_rng(seed).choice((1.0, -1.0), size=(n_perm, len(d)))
    return float((1 + np.sum(signs @ d >= obs - tol)) / (n_perm + 1))


def _two_sided_flip(d: Sequence[float], n_perm: int = N_PERM, seed: int = 0) -> float:
    d = np.asarray(d, dtype=float)
    if not len(d):
        return math.nan
    return min(1.0, 2 * min(_one_sided_flip(d, n_perm, seed), _one_sided_flip(-d, n_perm, seed)))


def build_session_report(
    run_dir: str | Path, out_dir: str | Path | None = None, n_boot: int = N_BOOT, seed: int = 0
) -> dict[str, Any]:
    """Score every agent in ``run_dir`` and write the three report files."""
    run_dir = Path(run_dir)
    runs, sessions, suite = _load(run_dir)
    keys = sorted(sessions)
    computed = []
    for ref in REFERENCES:
        have = runs.get(ref, {})
        if set(have) != set(keys):
            runs[ref] = {**_computed(ref, {k: sessions[k] for k in keys if k not in have}), **have}
            computed.append(ref)
    tiers = _tiers(sessions)
    by_tier = {t: [k for k in keys if sessions[k]["tier"] == t] for t in tiers}
    need_ref = [t for t in tiers if CEILING.get(t, (100.0,))[0] < SECOND_COLUMN_BELOW]
    if need_ref and set(runs.get(REF_PUBLIC, {})) != set(keys):
        missing = {k: sessions[k] for k in keys if k not in runs.get(REF_PUBLIC, {})}
        runs[REF_PUBLIC] = {**_computed(REF_PUBLIC, missing), **runs.get(REF_PUBLIC, {})}
        computed.append(REF_PUBLIC)
    oracle = {k: runs[ORACLE][k].xpnl_alpha for k in keys}
    boot = _Boot(by_tier, n_boot, seed)
    o_draw = {t: boot.sums(oracle, [t]) for t in tiers}
    o_tot = {t: sum(oracle[k] for k in by_tier[t]) for t in tiers}

    def share(vals: Mapping[Key, float], ts: Sequence[str]) -> dict[str, float]:
        num = sum(vals[k] for t in ts for k in by_tier[t])
        den = sum(o_tot[t] for t in ts)
        # ratio first: the oracle then scores exactly 100 in every draw on every machine
        draws = 100 * (boot.sums(vals, ts) / sum(o_draw[t] for t in ts))
        return _interval(100 * (num / den), draws)

    # ceiling lines: per tier and pooled (oracle-weighted)
    ceiling: dict[str, Any] = {"tag": CEILING_TAG}
    total_o = sum(o_tot.values())
    for t in tiers:
        if t in CEILING:
            est, lo, hi = CEILING[t]
            ceiling[t] = {"value": est, "lo": lo, "hi": hi}
    if all(t in CEILING for t in tiers):
        ceiling["pooled"] = {
            name: sum(CEILING[t][i] * o_tot[t] for t in tiers) / total_o
            for i, name in enumerate(("value", "lo", "hi"))
        }

    agents: list[dict[str, Any]] = []
    for name, per in runs.items():
        complete = set(per) == set(keys)
        if not complete:
            continue
        a: dict[str, Any] = {
            "agent": name,
            "setup": split_replicate(name)[0],
            "replicate": split_replicate(name)[1],
            "llm": is_llm(name),
            "computed": name in computed,
            "sessions": len(per),
            "quotes": sum(m.n_quotes for m in per.values()),
        }
        x = {k: per[k].xpnl_alpha for k in keys}
        a["pooled"] = share(x, tiers)
        a["tiers"] = {t: share(x, [t]) for t in tiers}
        if "open" in tiers and "mixed" in tiers:
            d_open = 100 * (boot.sums(x, ["open"]) / o_draw["open"])
            d_mixed = 100 * (boot.sums(x, ["mixed"]) / o_draw["mixed"])
            gap = a["tiers"]["open"]["value"] - a["tiers"]["mixed"]["value"]
            a["gradient"] = _interval(gap, d_open - d_mixed)
        if REF_PUBLIC in runs:
            ref = runs[REF_PUBLIC]
            a["share_of_ref"] = {
                t: 100 * sum(x[k] for k in by_tier[t]) / sum(ref[k].xpnl_alpha for k in by_tier[t])
                for t in need_ref
            }
        regimes: dict[str, Any] = {}
        for t in tiers:
            cell = {}
            for r in sorted({per[k].regime for k in by_tier[t]}):
                ks = [k for k in by_tier[t] if per[k].regime == r]
                own, orc = sum(x[k] for k in ks), sum(oracle[k] for k in ks)
                cell[str(r)] = {
                    "alpha": per[ks[0]].alpha,
                    "sessions": len(ks),
                    "share": 100 * own / orc if orc > 0 else math.nan,
                    "per_session": own / len(ks),
                }
            regimes[t] = cell
        a["by_regime"] = regimes
        terms: dict[str, Any] = {}
        for t in [*tiers, "pooled"]:
            ks = keys if t == "pooled" else by_tier[t]
            den = sum(oracle[k] for k in ks) / 100
            pricing = sum(per[k].pricing for k in ks)
            info = sum(per[k].information for k in ks)
            path = sum(oracle[k] - per[k].oracle_local for k in ks)
            resid = sum(per[k].residual for k in ks)
            short = sum(oracle[k] - x[k] for k in ks)
            terms[t] = {
                "shortfall": short / den,
                "pricing": pricing / den,
                "information": info / den,
                "path": path / den,
                "residual": resid / den,
            }
        a["shortfall"] = terms
        widths = {
            k: np.array([per[k].half, per[k].half_bayes, per[k].half_prior]).reshape(3, -1)
            for k in keys
        }
        draws = []
        rng = np.random.default_rng(seed + 1)
        for _ in range(n_boot // 4):
            pick = [ks[i] for t, ks in by_tier.items() for i in rng.integers(0, len(ks), len(ks))]
            draws.append(learning_response(*np.concatenate([widths[k] for k in pick], axis=1)))
        a["learning_response"] = _interval(
            learning_response(*np.concatenate([widths[k] for k in keys], axis=1)), np.array(draws)
        )
        n_rounds = len(next(iter(per.values())).alpha_mass)
        a["alpha_mass"] = [
            float(np.mean([per[k].alpha_mass[r] for k in keys])) for r in range(n_rounds)
        ]
        tw = sum(m.n_width for m in per.values())
        a["width_ratio"] = (
            sum(m.width for m in per.values()) / sum(m.bayes_width for m in per.values())
            if tw
            else math.nan
        )
        early = sum(m.early_two_sided for m in per.values())
        a["probing_share"] = (
            sum(m.early_tighter for m in per.values()) / early if early else math.nan
        )
        nm = sum(m.n_mid for m in per.values())
        a["mid_error"] = sum(m.mid_err for m in per.values()) / nm if nm else math.nan
        a["invalid_rate"] = sum(m.invalid for m in per.values()) / a["quotes"]
        a["no_quote_rate"] = sum(m.no_quote for m in per.values()) / a["quotes"]
        costs = [m.cost_usd for m in per.values()]
        a["cost_usd"] = None if any(c is None for c in costs) else float(sum(costs))
        a["output_tokens_per_quote"] = sum(m.output_tokens for m in per.values()) / a["quotes"]
        a["per_session"] = {f"{k[0]}/{k[1]}": x[k] for k in keys}
        agents.append(a)
    agents.sort(key=lambda a: -a["pooled"]["value"])
    # an LLM run is read against the reference quoters' rows: name the ones that are absent
    missing = []
    if any(a["llm"] for a in agents):
        from mmarena.agents.session_baselines import SESSION_BASELINES

        missing = sorted(set(SESSION_BASELINES) - {a["agent"] for a in agents})

    summary: dict[str, Any] = {
        "run_dir": run_dir.as_posix(),
        "suite": suite,
        "trace_version": 3,
        "score": "100 x sum(ev_alpha) / sum(oracle ev_alpha), prior-sd units",
        "tiers": tiers,
        "sessions": len(keys),
        "oracle_per_session": {t: o_tot[t] / len(by_tier[t]) for t in tiers},
        "ceiling": ceiling,
        "second_column": {"tiers": need_ref, "reference": REF_PUBLIC, "tag": REF_TAG},
        "computed_references": computed,
        "missing_baselines": missing,
        "agents": agents,
        "replicates": _replicates(agents),
        "tests": _tests(agents, runs, by_tier, keys, seed),
    }
    out = Path(out_dir) if out_dir else run_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(_clean(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "leaderboard.csv").write_text(_csv(agents, tiers), encoding="utf-8", newline="\n")
    (out / "REPORT.md").write_text(render(summary), encoding="utf-8", newline="\n")
    return summary


def _per_session(a: Mapping[str, Any]) -> dict[str, float]:
    return dict(a["per_session"])


def _replicates(agents: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    setups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for a in agents:
        if a["llm"]:
            setups[a["setup"]].append(a)
    rows = {}
    for setup, rs in setups.items():
        if len(rs) < 2:
            continue
        scores = [r["pooled"]["value"] for r in sorted(rs, key=lambda r: r["replicate"])]
        rows[setup] = {"runs": len(rs), "scores": scores, "sd": float(np.std(scores, ddof=1))}
    pairs = []
    names = sorted(rows)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            t, df, p = welch(rows[a]["scores"], rows[b]["scores"])
            gap = float(np.mean(rows[a]["scores"]) - np.mean(rows[b]["scores"]))
            pooled_sd = math.sqrt((rows[a]["sd"] ** 2 + rows[b]["sd"] ** 2) / 2)
            pairs.append(
                {"a": a, "b": b, "gap": gap, "pooled_sd": pooled_sd, "t": t, "df": df, "p": p}
            )
    return {"setups": rows, "pairs": pairs}


def _setup_means(agents: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    """Run-averaged per-session values of each LLM setup."""
    acc: dict[str, list[dict[str, float]]] = defaultdict(list)
    for a in agents:
        if a["llm"]:
            acc[a["setup"]].append(_per_session(a))
    return {s: {k: float(np.mean([r[k] for r in rs])) for k in rs[0]} for s, rs in acc.items()}


def _tests(
    agents: Sequence[Mapping[str, Any]],
    runs: Mapping[str, Mapping[Key, SessionMetrics]],
    by_tier: Mapping[str, list[Key]],
    keys: Sequence[Key],
    seed: int,
) -> dict[str, Any]:
    """The pre-registered families (docs/prereg-core-v2.md), Holm-adjusted within each."""
    means = _setup_means(agents)
    if not means:
        return {}
    ks = [f"{k[0]}/{k[1]}" for k in keys]
    mixed = [f"{k[0]}/{k[1]}" for k in by_tier.get("mixed", [])]
    ref = {n: {f"{k[0]}/{k[1]}": runs[n][k].xpnl_alpha for k in keys} for n in REFERENCES}
    lr = {a["setup"]: a["learning_response"] for a in agents if a["llm"] and a["replicate"] == 1}
    fam_a, fam_b, fam_c = [], [], []
    setups = sorted(means)
    for i, a in enumerate(setups):
        for b in setups[i + 1 :]:
            d = [means[a][k] - means[b][k] for k in ks]
            fam_a.append({"test": f"{a} vs {b}, pooled", "p": _two_sided_flip(d, seed=seed)})
    for s in setups:
        if s in lr:
            fam_b.append(
                {
                    "test": f"{s}: learning response > 0",
                    "value": lr[s]["value"],
                    "p": lr[s]["p_le0"],
                }
            )
        for other in ("bayes-nolearn", "bayes"):
            if mixed:
                d = [means[s][k] - ref[other][k] for k in mixed]
                fam_b.append({"test": f"{s} > {other}, mixed tier", "p": _one_sided_flip(d)})
    by_setup = {a["setup"]: a for a in agents if a["llm"] and a["replicate"] == 1}
    for s, a in by_setup.items():
        if "gradient" in a:
            g = a["gradient"]
            fam_c.append(
                {"test": f"{s}: open share > mixed share", "value": g["value"], "p": g["p_le0"]}
            )
        if s.endswith("@high"):
            low = s[: -len("@high")] + "@low"
            if low in means:
                d = [means[s][k] - means[low][k] for k in ks]
                fam_c.append({"test": f"{s} > {low}, pooled", "p": _one_sided_flip(d)})
    for fam in (fam_a, fam_b, fam_c):
        for row, adj in zip(fam, holm([r["p"] for r in fam]), strict=True):
            row["p_holm"] = adj
    return {"A": fam_a, "B": fam_b, "C": fam_c}


def _csv(agents: Sequence[Mapping[str, Any]], tiers: Sequence[str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    head = ["agent", "pooled", "pooled_lo", "pooled_hi"]
    for t in tiers:
        head += [t, f"{t}_lo", f"{t}_hi"]
    head += ["learning_response", "sessions", "quotes", "invalid_rate", "cost_usd"]
    w.writerow(head)
    for a in agents:
        row: list[Any] = [a["agent"]]
        for e in [a["pooled"], *(a["tiers"][t] for t in tiers)]:
            row += [f"{e['value']:.4f}", f"{e['lo']:.4f}", f"{e['hi']:.4f}"]
        lr = a["learning_response"]["value"]
        cost = a["cost_usd"]
        row += [
            f"{lr:.4f}" if math.isfinite(lr) else "",
            a["sessions"],
            a["quotes"],
            f"{a['invalid_rate']:.4f}",
            "" if cost is None else f"{cost:.4f}",
        ]
        w.writerow(row)
    return buf.getvalue()


def _e(e: Mapping[str, float], nd: int = 1) -> str:
    return _ci(e["value"], e["lo"], e["hi"], nd)


def _lr(a: Mapping[str, Any]) -> str:
    e = a["learning_response"]
    return _e(e, 2) if math.isfinite(e["value"]) else "-"


def _ceiling_cell(c: Mapping[str, float] | None) -> str:
    if not c:
        return "-"
    return f"about {c['value']:.0f} ({c['lo']:.0f} to {c['hi']:.0f})"


def render(s: Mapping[str, Any]) -> str:
    tiers = s["tiers"]
    ceiling = s["ceiling"]
    second = s["second_column"]["tiers"]
    agents = s["agents"]
    lines = [f"# mm-arena session report: {s['suite']}", ""]
    lines.append(
        f"{s['sessions']} sessions. Score: share of the known-regime oracle's expected profit, "
        "`100 x sum(ev_alpha) / sum(oracle ev_alpha)`, each session in prior-sd units of its "
        "game. 100 is the profit of a quoter who is told the informed share and quotes the "
        "myopic optimum for it; 0 is never quoting; negative means an expected loss. Intervals: "
        "95%, bootstrap over sessions within each tier."
    )
    lines.append("")
    lines.append(
        f"The ceiling line (`{ceiling['tag']}`) is an estimate of the best score a quoter that "
        "does not know the informed share can reach, with its bracket. It is not a denominator "
        "and later versions may tighten it."
    )
    if second:
        lines.append(
            f"For tiers whose ceiling is below {SECOND_COLUMN_BELOW:.0f} the leaderboard adds the "
            f"share of the best public quoter run so far (`{s['second_column']['reference']}`, "
            f"tag `{s['second_column']['tag']}`): a provisional reading aid, not the score."
        )
    if s["computed_references"]:
        refs = ", ".join(f"`{n}`" for n in s["computed_references"])
        lines.append(f"Computed from the session specs (no traces in this directory): {refs}.")
    if s["missing_baselines"]:
        names = ", ".join(f"`{n}`" for n in s["missing_baselines"])
        lines.append(
            f"Reference quoters without a row here: {names}. `mm-arena run --agent baselines` on "
            "the same suite and run directory adds them."
        )
    lines += ["", "## Leaderboard", ""]
    head = ["agent", "pooled", *tiers]
    head += [f"{t}, % of {s['second_column']['tag']}" for t in second]
    head += ["learning response", "invalid %", "cost USD"]
    rows = []
    for a in agents:
        r = [f"`{a['agent']}`", _e(a["pooled"]), *(_e(a["tiers"][t]) for t in tiers)]
        r += [_f(a.get("share_of_ref", {}).get(t), 1) for t in second]
        r += [
            _lr(a),
            _f(a["invalid_rate"], 1, pct=True),
            "-" if a["cost_usd"] is None or not a["llm"] else f"{a['cost_usd']:.2f}",
        ]
        rows.append(r)
    ceil_row = [
        f"ceiling (estimate, `{ceiling['tag']}`)",
        _ceiling_cell(ceiling.get("pooled")),
        *(_ceiling_cell(ceiling.get(t)) for t in tiers),
    ]
    ceil_row += ["-" for _ in second] + ["-", "-", "-"]
    rows.append(ceil_row)
    lines += _table(head, rows)
    lines += [
        "",
        "Oracle profit per session (prior sd): "
        + ", ".join(f"{t} {s['oracle_per_session'][t]:.2f}" for t in tiers)
        + ".",
        "",
        "## Score by true regime",
        "",
        "Share of the oracle within each regime, and for the most informed regime the expected "
        "profit per session in prior sd (the oracle earns little there, so a share is unstable).",
        "",
    ]
    head = ["agent"]
    first = agents[0]["by_regime"] if agents else {}
    top = max((c["alpha"] for t in tiers for c in first.get(t, {}).values()), default=0.0)
    for t in tiers:
        for cell in first.get(t, {}).values():
            unit = " (sd per session)" if cell["alpha"] == top else ""
            head.append(f"{t}, alpha {cell['alpha']:g}{unit}")
    rows = []
    for a in agents:
        r = [f"`{a['agent']}`"]
        for t in tiers:
            for cell in a["by_regime"][t].values():
                informed = cell["alpha"] == top
                r.append(f"{cell['per_session']:+.2f}" if informed else _f(cell["share"], 1))
        rows.append(r)
    lines += _table(head, rows)
    lines += [
        "",
        "## Shortfall to the oracle",
        "",
        "In oracle points: shortfall = pricing + information + path + residual, exactly. "
        "Pricing: expected profit given up against the myopic Bayes quote given public "
        "information. Information: what not knowing the informed share still costs at the "
        "agent's states. Path: the oracle on its own path minus the oracle at the agent's "
        "states. Residual: regime luck of the agent's quotes against the Bayes quotes at the "
        "same states (zero in expectation for public quote rules).",
        "",
    ]
    rows = []
    for a in agents:
        for t in [*tiers, "pooled"]:
            d = a["shortfall"][t]
            rows.append(
                [f"`{a['agent']}`", t]
                + [_f(d[k], 1) for k in ("shortfall", "pricing", "information", "path", "residual")]
            )
    lines += _table(
        ["agent", "tier", "shortfall", "pricing", "information", "path", "residual"], rows
    )
    n_rounds = len(agents[0]["alpha_mass"]) if agents else 0
    lines += [
        "",
        "## Skill axes",
        "",
        "Learning response: coefficient on the myopic Bayes quote's half-width when the agent's "
        "half-width is regressed on the Bayes and the prior-regime half-widths together, at the "
        "same states (1: widths follow the evidence on the informed share as the Bayes quote "
        "does; 0: they follow the prior-regime quote or neither). Mass on truth: mean posterior "
        "mass on the true regime at the start of each round, along the agent's own path. "
        "Probing: share of two-sided quotes in rounds 1 and 2 tighter than the Bayes quote. "
        "Width: total width over the Bayes quote's at the same states. Mid error: mean "
        "|mid - public mean| in public posterior sds.",
        "",
    ]
    rows = []
    for a in agents:
        mass = " / ".join(f"{m:.2f}" for m in a["alpha_mass"])
        rows.append(
            [
                f"`{a['agent']}`",
                _lr(a),
                mass,
                _f(a["probing_share"], 0, pct=True),
                _f(a["width_ratio"], 2),
                _f(a["mid_error"], 2),
            ]
        )
    lines += _table(
        [
            "agent",
            "learning response",
            f"mass on truth, rounds 1-{n_rounds}",
            "probing %",
            "width",
            "mid error",
        ],
        rows,
    )
    rep = s["replicates"]
    if rep.get("setups"):
        lines += ["", "## Run-to-run variability", ""]
        rows = [
            [f"`{k}`", str(v["runs"]), ", ".join(f"{x:.1f}" for x in v["scores"]), f"{v['sd']:.2f}"]
            for k, v in sorted(rep["setups"].items())
        ]
        lines += _table(["setup", "runs", "pooled scores", "run SD"], rows)
        if rep["pairs"]:
            lines.append("")
            rows = [
                [
                    f"`{p['a']}` - `{p['b']}`",
                    f"{p['gap']:+.1f}",
                    f"{p['pooled_sd']:.2f}",
                    f"{p['t']:.2f} ({p['df']:.1f})" if math.isfinite(p["t"]) else "-",
                    _p(p["p"]),
                ]
                for p in rep["pairs"]
            ]
            lines += _table(["pair", "gap", "pooled run SD", "Welch t (df)", "p"], rows)
    tests = s["tests"]
    if tests:
        lines += [
            "",
            "## Pre-registered tests",
            "",
            "Families as in `docs/prereg-core-v2.md`; p-values Holm-adjusted within each family. "
            "Paired tests are sign flips of per-session differences of run-averaged values.",
        ]
        for fam, title in (
            ("A", "separation"),
            ("B", "learning and probing"),
            ("C", "gradient and effort"),
        ):
            if not tests.get(fam):
                continue
            lines += ["", f"Family {fam} ({title})", ""]
            rows = [
                [r["test"], _f(r.get("value") if isinstance(r.get("value"), float) else None, 1),
                 _p(r["p"]), _p(r["p_holm"])]
                for r in tests[fam]
            ]  # fmt: skip
            lines += _table(["test", "value", "p", "p (Holm)"], rows)
    lines.append("")
    return "\n".join(lines)
