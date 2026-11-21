"""Baseline ladder on a sample of sessions: share of the known-regime oracle per tier.

    uv run python scripts/headroom_v2.py --sessions 150 [--base 50000] [--agents a,b,...]
        [--tiers open=0.85,mixed=0.7,tight=0.5] [--rounds 6] [--out tmp/headroom_v2.jsonl]

The sample has ``sessions / 5`` games per family and tier, game seeds
``base + 1000 * (family + 1) + 100 * tier + i`` (families dice, cards, transform, coin, urn;
tiers in the order given) and the true regime of game ``i`` in each block from a seeded
permutation, ``perm[i % 3]`` with ``perm = default_rng([base, tier, family]).permutation(3)``,
so each regime is equally frequent when ``sessions / 5`` is a multiple of 3. The default tiers
are the released ones (core-v2's open and mixed, tight-v2's tight); with the default base this
is the sample behind the tier table of ``docs/methodology-v2.md``.

One JSON line per (session, agent) is appended to ``--out`` as it finishes; a rerun skips the
pairs already there. The table is the ratio of sums of ``ev_alpha`` (in prior-sd units) to the
oracle's, with 95% intervals from a bootstrap over games within each tier (2,000 draws).
Runs on ``--workers`` processes (default 4).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from mmarena.agents.session_baselines import SESSION_BASELINES
from mmarena.joint import Regimes
from mmarena.session_engine import run_session
from mmarena.sessions import Session, make_session

FAMILIES = ("dice", "cards", "transform", "coin", "urn")
REGIMES = Regimes.of([0.05, 0.5, 0.9])
DEFAULT_TIERS = "open=0.85,mixed=0.7,tight=0.5"
DEFAULT_AGENTS = (
    "oracle,bayes,bayes-optimist,bayes-thompson,bayes-nolearn,bayes-fixed-low,"
    "bayes-fixed-high,bayes-noflow,bayes-mean,glosten-milgrom,static"
)


def sample(per_tier: int, base: int, tiers: dict[str, float], rounds: int = 6) -> list[Session]:
    if per_tier % len(FAMILIES):
        raise SystemExit(f"--sessions must be a multiple of {len(FAMILIES)}")
    per_block = per_tier // len(FAMILIES)
    out = []
    for ti, (tier, ratio) in enumerate(tiers.items()):
        for fi, fam in enumerate(FAMILIES):
            perm = np.random.default_rng([base, ti, fi]).permutation(REGIMES.k)
            for i in range(per_block):
                seed = base + 1000 * (1 + fi) + 100 * ti + i
                out.append(make_session(fam, seed, ratio, REGIMES, int(perm[i % 3]), rounds, tier))
    return out


def _work(job: tuple[Session, str]) -> dict:
    session, name = job
    started = time.perf_counter()
    tr = run_session(session, SESSION_BASELINES[name](), 0)
    sd = session.game.prior_std
    return {
        "session": session.id,
        "agent": name,
        "tier": session.tier,
        "family": session.game.family,
        "regime": session.regime,
        "xpnl_alpha": tr["xpnl_alpha"] / sd,
        "xpnl": tr["xpnl"] / sd,
        "rounds": [r["xpnl_alpha"] / sd for r in tr["rounds"]],
        "seconds": round(time.perf_counter() - started, 2),
    }


def ladder(rows: list[dict], tiers: list[str], n_boot: int = 2000, seed: int = 0) -> list[str]:
    """Markdown table: share of the oracle per tier and pooled, with stratified intervals."""
    val: dict[tuple[str, str], float] = {(r["agent"], r["session"]): r["xpnl_alpha"] for r in rows}
    tier_of = {r["session"]: r["tier"] for r in rows}
    agents = sorted({r["agent"] for r in rows}, key=lambda a: (a != "oracle", a))
    sessions = {t: sorted(s for s, tt in tier_of.items() if tt == t) for t in tiers}
    rng = np.random.default_rng(seed)
    draws = {t: rng.integers(0, len(sessions[t]), (n_boot, len(sessions[t]))) for t in tiers}
    lines = [
        "| quoter | " + " | ".join(tiers) + " | pooled |",
        "| --- |" + " ---: |" * (len(tiers) + 1),
    ]
    for a in agents:
        if not all((a, s) in val for t in tiers for s in sessions[t]):
            continue
        cells, num_b, den_b, num, den = [], 0.0, 0.0, 0.0, 0.0
        for t in tiers:
            x = np.array([val[(a, s)] for s in sessions[t]])
            o = np.array([val[("oracle", s)] for s in sessions[t]])
            xb, ob = x[draws[t]].sum(axis=1), o[draws[t]].sum(axis=1)
            lo, hi = np.quantile(100 * xb / ob, [0.025, 0.975])
            cells.append(f"{100 * x.sum() / o.sum():.1f} [{lo:.1f}, {hi:.1f}]")
            num, den, num_b, den_b = num + x.sum(), den + o.sum(), num_b + xb, den_b + ob
        lo, hi = np.quantile(100 * num_b / den_b, [0.025, 0.975])
        cells.append(f"{100 * num / den:.1f} [{lo:.1f}, {hi:.1f}]")
        lines.append(f"| `{a}` | " + " | ".join(cells) + " |")
    return lines


def parse_tiers(text: str) -> dict[str, float]:
    return {k: float(v) for k, v in (p.split("=") for p in text.split(","))}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sessions", type=int, default=150, help="sessions per tier")
    p.add_argument("--base", type=int, default=50000)
    p.add_argument("--agents", default=DEFAULT_AGENTS)
    p.add_argument("--tiers", default=DEFAULT_TIERS)
    p.add_argument("--rounds", type=int, default=6)
    p.add_argument("--out", default="tmp/headroom_v2.jsonl")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--report-only", action="store_true", help="print the table, run nothing")
    args = p.parse_args()
    tiers = parse_tiers(args.tiers)
    agents = args.agents.split(",")
    if unknown := [a for a in agents if a not in SESSION_BASELINES]:
        sys.exit(f"unknown agent(s): {unknown}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pool_sessions = sample(args.sessions, args.base, tiers, args.rounds)
    ids = {s.id for s in pool_sessions}
    rows = (
        [json.loads(ln) for ln in out.read_text().splitlines() if ln.strip()]
        if out.exists()
        else []
    )
    rows = [r for r in rows if r["session"] in ids]
    done = {(r["session"], r["agent"]) for r in rows}
    jobs = [(s, a) for a in agents for s in pool_sessions if (s.id, a) not in done]
    if jobs and not args.report_only:
        started = time.time()
        print(f"{len(jobs)} runs to do ({len(done)} done) -> {out}", file=sys.stderr, flush=True)
        with Pool(args.workers) as pool, out.open("a", encoding="utf-8", newline="\n") as fh:
            for i, row in enumerate(pool.imap_unordered(_work, jobs, chunksize=1), 1):
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                rows.append(row)
                if i % 25 == 0 or i == len(jobs):
                    rate = i / (time.time() - started)
                    eta = (len(jobs) - i) / rate / 60
                    print(
                        f"{i}/{len(jobs)} {rate:.2f}/s eta {eta:.0f} min",
                        file=sys.stderr,
                        flush=True,
                    )
    print("\n".join(ladder(rows, list(tiers))))


if __name__ == "__main__":
    main()
