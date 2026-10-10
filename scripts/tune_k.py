"""Tune the ``bayes-mean`` half-width ``k`` (posterior sds) on a held-out tuning set.

The tuning set has the families, variants and generator of core-v1 (5 families x (4 classic +
8 perturbed) games, 2 episodes each) but game seeds offset by ``SEED_OFFSET`` and episode seeds
starting at ``EPISODE_OFFSET``, so it shares no game or episode with core-v1 or full-v1. For each
``k`` on the grid it plays ``bayes-mean`` and reports 100 * sum(xpnl) / sum(xpnl of ``bayes``)
on the same episodes, each xpnl in units of the game's prior sd (the report's headline).
Fills depend on the quote, so each ``k`` is a separate set of episodes.

Usage: ``uv run python scripts/tune_k.py [--workers N] [--step 0.05] [--max-k 3.0]``
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from mmarena.agents.baselines import BayesAgent, MeanAgent
from mmarena.engine import run_episode
from mmarena.games import Game, make_game
from mmarena.suite import load_suite

SEED_OFFSET = 100_000  # core-v1 and full-v1 game seeds are all below 10 000
EPISODE_OFFSET = 1_000  # core-v1 uses episode seeds 0-1, full-v1 0-2


def tuning_games() -> list[Game]:
    """Core-v1 layout from offset seeds, skipping any game whose content id is in core/full-v1.

    Classic games differ only in their random market, so a few collide with suite games by
    chance; those seeds are skipped to keep the tuning set content-disjoint as well.
    """
    core = load_suite("core-v1")
    used = {g.id for s in (core, load_suite("full-v1")) for g in s.games()}
    games: list[Game] = []
    for b in core.blocks:
        seed, made = b.seed + SEED_OFFSET, 0
        while made < b.games:
            g = make_game(b.family, seed, b.variant)
            seed += 1
            if g.id in used:
                continue
            used.add(g.id)
            made += 1
            games.append(g)
    return games


def _play(args: tuple[str, str, int, int, list[float]]) -> tuple[np.ndarray, float]:
    family, variant, seed, n_episodes, ks = args
    game = make_game(family, seed, variant)
    num = np.zeros(len(ks))
    den = 0.0
    sd = game.prior_std or 1.0  # the headline pools xpnl in prior-sd units
    for e in range(n_episodes):
        ep = EPISODE_OFFSET + e
        den += run_episode(game, BayesAgent(), ep)["xpnl"] / sd
        for i, k in enumerate(ks):
            num[i] += run_episode(game, MeanAgent(k), ep)["xpnl"] / sd
    return num, den


def sweep(games: list[Game], n_episodes: int, ks: list[float], workers: int) -> np.ndarray:
    jobs = [(g.family, g.variant, int(g.seed or 0), n_episodes, ks) for g in games]
    num, den = np.zeros(len(ks)), 0.0
    with ProcessPoolExecutor(workers) as pool:
        for n, d in pool.map(_play, jobs):
            num += n
            den += d
    return 100.0 * num / den


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--max-k", type=float, default=3.0)
    args = ap.parse_args()
    games = tuning_games()
    n_episodes = load_suite("core-v1").episodes
    ks = [round(float(k), 4) for k in np.arange(0.0, args.max_k + 1e-9, args.step)]
    print(f"tuning set: {len(games)} games x {n_episodes} episodes, {len(ks)} values of k")
    started = time.perf_counter()
    edge = sweep(games, n_episodes, ks, args.workers)
    for k, e in zip(ks, edge, strict=True):
        print(f"k={k:5.2f}  edge={e:7.2f}")
    best = int(np.argmax(edge))
    print(f"argmax k={ks[best]:.2f}  edge={edge[best]:.2f}  ({time.perf_counter() - started:.0f}s)")


if __name__ == "__main__":
    main()
