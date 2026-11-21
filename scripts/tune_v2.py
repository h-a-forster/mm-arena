"""Tune ``bayes-mean``'s k and ``bayes-optimist``'s gamma for session suites.

    uv run python scripts/tune_v2.py [--sessions 60] [--base 130000] [--tiers open=0.85,mixed=0.7]

The tuning sample is ``scripts/headroom_v2.py``'s layout at base seed 130000: game seeds
131000-135299, disjoint from every released suite (30000-35299, smoke-v2 35000-35200) and from
the seeds of the ladder samples (50000-95299). The objective is the pooled share of the
oracle on the given tiers (the core-v2 tiers by default). Prints the share of every candidate
and the argmax; the constants live in ``mmarena.agents.session_baselines``.
"""

from __future__ import annotations

import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from headroom_v2 import parse_tiers, sample  # noqa: E402

from mmarena.agents.session_baselines import OptimistAgent, OracleAgent, SessionBayes  # noqa: E402
from mmarena.session_engine import run_session  # noqa: E402
from mmarena.sessions import Session  # noqa: E402

DEFAULT_TIERS = "open=0.85,mixed=0.7"
KS = (0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4)
GAMMAS = (0.5, 1.0, 2.0, 4.0, 8.0)


def _agent(kind: str, value: float):
    if kind == "oracle":
        return OracleAgent()
    if kind == "k":
        return SessionBayes("bayes-mean", rule="mean", k=value)
    return OptimistAgent(gamma=value)


def _work(job: tuple[Session, str, float]) -> tuple[str, float, str, float]:
    session, kind, value = job
    tr = run_session(session, _agent(kind, value), 0)
    return kind, value, session.id, tr["xpnl_alpha"] / session.game.prior_std


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sessions", type=int, default=60, help="sessions per tier")
    p.add_argument("--base", type=int, default=130000)
    p.add_argument("--tiers", default=DEFAULT_TIERS)
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    pool_sessions = sample(args.sessions, args.base, parse_tiers(args.tiers))
    jobs = [(s, "oracle", 0.0) for s in pool_sessions]
    jobs += [(s, "k", k) for k in KS for s in pool_sessions]
    jobs += [(s, "gamma", g) for g in GAMMAS for s in pool_sessions]
    with Pool(args.workers) as pool:
        out = pool.map(_work, jobs, chunksize=4)
    oracle = sum(v for kind, _, _, v in out if kind == "oracle")
    for kind, grid in (("k", KS), ("gamma", GAMMAS)):
        shares = {x: 100 * sum(v for kd, val, _, v in out if kd == kind and val == x) / oracle
                  for x in grid}  # fmt: skip
        for x, s in shares.items():
            print(f"{kind} {x:g}: {s:.1f}")
        best = max(shares, key=shares.get)
        print(f"argmax {kind} = {best:g} ({shares[best]:.1f})\n")


if __name__ == "__main__":
    main()
