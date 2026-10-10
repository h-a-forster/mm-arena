"""How much does a less myopic quoter gain over ``bayes``? One-step lookahead on a suite.

Plays ``bayes`` and ``bayes-lookahead`` on the same (game, seed) episodes and prints the
lookahead's edge captured (100 * sum xpnl / sum xpnl of ``bayes``) with a game-clustered 95%
bootstrap interval, the paired difference to 100, and the runtime. The lookahead maximises
immediate plus next-step expected myopic profit on a candidate grid around the myopic quote
(see ``LookaheadAgent``); its edge above 100 is a lower bound on the headroom of the myopic
reference, since a deeper horizon or a finer grid could only add to it.

Usage: ``uv run python scripts/headroom.py [--suite core-v1] [--workers 4] [--max-games N]
[--steps 8] [--res 16]``. ``--max-games`` keeps the first N games of the suite (all by default).
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from mmarena.agents.baselines import LOOKAHEAD_RES, LOOKAHEAD_STEPS, BayesAgent, LookaheadAgent
from mmarena.engine import run_episode
from mmarena.stats import bootstrap_ratio, paired_difference
from mmarena.suite import load_suite


def _play(
    args: tuple[str, int, float, int],
) -> tuple[str, float, float, float]:  # (game id, bayes, lookahead xpnl in prior-sd units, s)
    from mmarena.games import make_game

    spec, steps, res, episode = args
    family, variant, gseed = spec.split("|")
    game = make_game(family, int(gseed), variant)
    sd = game.prior_std or 1.0  # xpnl in prior-sd units, as in the report headline
    ref = run_episode(game, BayesAgent(), episode)["xpnl"] / sd
    t0 = time.perf_counter()
    la = run_episode(game, LookaheadAgent(steps=steps, res=res), episode)["xpnl"] / sd
    return game.id, ref, la, time.perf_counter() - t0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--suite", default="core-v1")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--max-games", type=int)
    ap.add_argument("--steps", type=int, default=LOOKAHEAD_STEPS, help="grid half-width in steps")
    ap.add_argument("--res", type=float, default=LOOKAHEAD_RES, help="grid step = sd / res")
    args = ap.parse_args()

    suite = load_suite(args.suite)
    games = list(suite.games())[: args.max_games]
    jobs = [
        (f"{g.family}|{g.variant}|{g.seed}", args.steps, args.res, e)
        for g in games
        for e in range(suite.episodes)
    ]
    print(f"{args.suite}: {len(games)} games x {suite.episodes} episodes, workers={args.workers}")
    started = time.perf_counter()
    with ProcessPoolExecutor(args.workers) as pool:
        rows = list(pool.map(_play, jobs))
    wall = time.perf_counter() - started

    ids = [r[0] for r in rows]
    ref = np.array([r[1] for r in rows])
    la = np.array([r[2] for r in rows])
    edge = bootstrap_ratio(100 * la, ref, ids)
    diff = paired_difference(la, ref, ref, ids, scale=100.0)
    print("bayes            100.00 (reference)")
    print(
        f"bayes-lookahead  {edge.value:6.2f} [{edge.lo:.2f}, {edge.hi:.2f}]  (game-clustered 95%)"
    )
    print(
        f"gain over bayes  {diff.diff.value:+.2f} [{diff.diff.lo:+.2f}, {diff.diff.hi:+.2f}] "
        f"points, sign-flip p={diff.p_value:.3g}, {diff.n_episodes} episodes, {diff.n_games} games"
    )
    per_ep = la - ref
    print(f"episodes where lookahead < bayes: {int((per_ep < -1e-9).sum())} of {len(rows)}")
    print(f"runtime: {wall:.0f}s wall, {sum(r[3] for r in rows):.0f}s lookahead CPU")


if __name__ == "__main__":
    main()
