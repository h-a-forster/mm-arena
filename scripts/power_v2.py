"""Projected run-to-run noise of a session suite under a decision-noise model.

    uv run python scripts/power_v2.py [--suite core-v2] [--seeds 8] [--bases bayes,...]

There are no LLM runs to measure run-to-run noise on, so it is projected: take a reference
quote, move its mid by Normal(0, 0.25 public posterior sds) and multiply its half-width by a
lognormal factor (bias -8%, sd 0.25), half of each variance drawn once per session and half
per quote. A noise seed stands for a run. On core-v1 the same model gives a run-to-run SD of
0.95 points, where the real setups have 1.5 to 2.0, so real noise is projected at 1.6 to 2.1
times the model's.

Prints, per reference quoter, the mean and SD across seeds of the pooled and tier scores; the
gaps "learns the informed share" (``bayes`` minus ``bayes-nolearn``) and "probes"
(``bayes-optimist`` minus ``bayes``) in run SDs; and the pre-registered replicate rule
``n = 2 (2.8 sigma / delta)^2`` runs per setup for a few smallest gaps of interest.
"""

from __future__ import annotations

import argparse
import math
import zlib
from multiprocessing import Pool

import numpy as np

from mmarena.agents.base import Quote
from mmarena.agents.session_baselines import SESSION_BASELINES, replay
from mmarena.joint import JointPosterior
from mmarena.session_engine import run_session
from mmarena.sessions import Session, SessionObservation, SessionSpec
from mmarena.suite import load_suite

MID_SD, WIDTH_BIAS, WIDTH_SD = 0.25, -0.08, 0.25
REAL_OVER_MODEL = (1.6, 2.1)


class NoisyAgent:
    """A reference quoter with decision noise; ``seed`` plays the role of a run.

    ``scale`` multiplies both noise sds (2 is about the real-to-modelled ratio on core-v1).
    """

    def __init__(self, base: str, seed: int, scale: float = 1.0) -> None:
        self.base = SESSION_BASELINES[base]()
        self.seed = seed
        self.scale = scale
        self.name = f"noisy-{base}#{seed}"
        self._rng: np.random.Generator | None = None

    def reset(self, spec: SessionSpec) -> None:
        self.base.reset(spec)
        self._rng = None

    def act(self, obs: SessionObservation) -> Quote:
        if self._rng is None:
            self._rng = np.random.default_rng([zlib.crc32(obs.session_id.encode()), 99, self.seed])
            self._e_mid, self._e_w = self._rng.standard_normal(2)
        q = self.base.act(obs)
        if q.bid is None or q.ask is None:
            return q
        z_mid, z_w = self._rng.standard_normal(2)
        r = math.sqrt(0.5)
        sd = max(
            replay(obs, JointPosterior(obs.game, obs.spec.regimes)).std(), obs.game.market.tick
        )
        mid = 0.5 * (q.bid + q.ask) + self.scale * MID_SD * sd * r * (self._e_mid + z_mid)
        width_noise = self.scale * WIDTH_SD * r * (self._e_w + z_w)
        half = 0.5 * (q.ask - q.bid) * math.exp(WIDTH_BIAS + width_noise)
        return Quote(mid - half, mid + half)


def _work(job: tuple[Session, str, int]) -> tuple[str, int, str, str, float]:
    session, base, seed = job
    agent = SESSION_BASELINES["oracle"]() if base == "oracle" else NoisyAgent(base, seed)
    tr = run_session(session, agent, 0)
    return base, seed, session.id, session.tier, tr["xpnl_alpha"] / session.game.prior_std


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--suite", default="core-v2")
    p.add_argument("--seeds", type=int, default=8)
    p.add_argument("--bases", default="bayes,bayes-nolearn,bayes-optimist")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    suite = load_suite(args.suite)
    sessions = list(suite.sessions())
    bases = args.bases.split(",")
    jobs = [(s, "oracle", 0) for s in sessions]
    jobs += [(s, b, k) for b in bases for k in range(args.seeds) for s in sessions]
    with Pool(args.workers) as pool:
        out = pool.map(_work, jobs, chunksize=2)
    tiers = [t for t in ("open", "mixed", "tight") if any(s.tier == t for s in sessions)]
    oracle = {t: sum(v for b, _, _, tt, v in out if b == "oracle" and tt == t) for t in tiers}
    scores: dict[str, dict[str, list[float]]] = {}
    for b in bases:
        scores[b] = {}
        for t in [*tiers, "pooled"]:
            ts = tiers if t == "pooled" else [t]
            den = sum(oracle[x] for x in ts)
            scores[b][t] = [
                100 * sum(v for bb, k, _, tt, v in out if bb == b and k == seed and tt in ts) / den
                for seed in range(args.seeds)
            ]
    print(f"{suite.name}: {len(sessions)} sessions, {args.seeds} noise seeds per quoter\n")
    print("| quoter | " + " | ".join(f"{t} mean (run SD)" for t in [*tiers, "pooled"]) + " |")
    print("| --- |" + " ---: |" * (len(tiers) + 1))
    for b in bases:
        cells = [f"{np.mean(v):.1f} ({np.std(v, ddof=1):.2f})" for v in scores[b].values()]
        print(f"| noisy `{b}` | " + " | ".join(cells) + " |")
    sd = {b: float(np.std(scores[b]["pooled"], ddof=1)) for b in bases}
    print()
    for a, b, label in (
        ("bayes", "bayes-nolearn", "learns"),
        ("bayes-optimist", "bayes", "probes"),
    ):
        if a in bases and b in bases:
            gap = float(np.mean(scores[a]["pooled"]) - np.mean(scores[b]["pooled"]))
            pooled_sd = math.sqrt((sd[a] ** 2 + sd[b] ** 2) / 2)
            print(f"{label}: {a} - {b} = {gap:+.1f} pooled points = {gap / pooled_sd:.1f} run SD")
    sigma = float(np.mean(list(sd.values())))
    print(f"\nmodel run SD (pooled, mean over quoters): {sigma:.2f}")
    for f in REAL_OVER_MODEL:
        s = f * sigma
        n = {d: math.ceil(2 * (2.8 * s / d) ** 2) for d in (3, 5, 10)}
        cells = ", ".join(f"delta {d}: {k}" for d, k in n.items())
        print(f"projected real SD {s:.1f} ({f}x): runs per setup {cells}")


if __name__ == "__main__":
    main()
