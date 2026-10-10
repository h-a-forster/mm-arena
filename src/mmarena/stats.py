"""Uncertainty for benchmark scores: game-clustered bootstrap, paired tests, power.

Episodes of the same game share the game's difficulty, so the unit of resampling is the game:
a bootstrap draw picks games with replacement and keeps all of their episodes. Everything is
seeded and deterministic.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from statistics import NormalDist

import numpy as np

N_BOOT = 2000
N_PERM = 10000
EXACT_PERM_MAX_CLUSTERS = 14


@dataclass(frozen=True)
class Estimate:
    value: float
    lo: float
    hi: float
    se: float

    def to_dict(self) -> dict[str, float]:
        return {"value": self.value, "lo": self.lo, "hi": self.hi, "se": self.se}


@dataclass(frozen=True)
class PairedResult:
    diff: Estimate
    p_value: float
    n_episodes: int
    n_games: int

    def to_dict(self) -> dict[str, float]:
        return {
            **{f"diff_{k}": v for k, v in self.diff.to_dict().items()},
            "p_value": self.p_value,
            "n_episodes": self.n_episodes,
            "n_games": self.n_games,
        }


def cluster_sums(
    clusters: Sequence[Hashable], *values: Sequence[float]
) -> tuple[list[Hashable], list[np.ndarray]]:
    """Sum each value array within clusters. Returns cluster labels (sorted) and the sums."""
    labels = sorted(set(clusters), key=str)
    index = {c: i for i, c in enumerate(labels)}
    idx = np.array([index[c] for c in clusters], dtype=int)
    sums = [
        np.bincount(idx, weights=np.asarray(v, dtype=float), minlength=len(labels)) for v in values
    ]
    return labels, sums


def bootstrap_counts(n_clusters: int, n_boot: int, seed: int) -> np.ndarray:
    """``(n_boot, n_clusters)`` matrix of how often each cluster is drawn."""
    rng = np.random.default_rng(seed)
    if n_clusters == 0:
        return np.zeros((n_boot, 0))
    return rng.multinomial(n_clusters, np.full(n_clusters, 1.0 / n_clusters), size=n_boot)


def _interval(value: float, draws: np.ndarray, level: float) -> Estimate:
    draws = draws[np.isfinite(draws)]
    if len(draws) == 0 or not math.isfinite(value):
        return Estimate(value, math.nan, math.nan, math.nan)
    a = (1 - level) / 2
    lo, hi = np.quantile(draws, [a, 1 - a])
    se = float(np.std(draws, ddof=1)) if len(draws) > 1 else 0.0
    return Estimate(value, float(lo), float(hi), se)


def _ratio(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den != 0, num / np.where(den != 0, den, 1.0), np.nan)


def bootstrap_ratio(
    num: Sequence[float],
    den: Sequence[float],
    clusters: Sequence[Hashable],
    scale: float = 1.0,
    n_boot: int = N_BOOT,
    seed: int = 0,
    level: float = 0.95,
) -> Estimate:
    """``scale * sum(num) / sum(den)`` with a game-clustered percentile interval."""
    _, (n_g, d_g) = cluster_sums(clusters, num, den)
    value = float(scale * _ratio(np.array(n_g.sum()), np.array(d_g.sum())))
    counts = bootstrap_counts(len(n_g), n_boot, seed)
    draws = scale * _ratio(counts @ n_g, counts @ d_g)
    return _interval(value, draws, level)


def bootstrap_mean(
    x: Sequence[float],
    clusters: Sequence[Hashable],
    n_boot: int = N_BOOT,
    seed: int = 0,
    level: float = 0.95,
) -> Estimate:
    """Mean over episodes with a game-clustered percentile interval."""
    return bootstrap_ratio(x, np.ones(len(x)), clusters, 1.0, n_boot, seed, level)


def bootstrap_pvalue(draws: Sequence[float] | np.ndarray) -> float:
    """Two-sided bootstrap p-value for "the statistic is 0": ``2 * min(P(d <= 0), P(d >= 0))``."""
    d = np.asarray(draws, dtype=float)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return math.nan
    return float(min(1.0, 2.0 * min(np.mean(d <= 0), np.mean(d >= 0))))


def _gap_draws(
    a: tuple[Sequence[float], Sequence[float], Sequence[Hashable]],
    b: tuple[Sequence[float], Sequence[float], Sequence[Hashable]],
    scale: float,
    n_boot: int,
    seed: int,
) -> tuple[float, np.ndarray]:
    _, (na, da) = cluster_sums(a[2], a[0], a[1])
    _, (nb, db) = cluster_sums(b[2], b[0], b[1])
    value = float(scale * (_ratio(na.sum(), da.sum()) - _ratio(nb.sum(), db.sum())))
    ca = bootstrap_counts(len(na), n_boot, seed)
    cb = bootstrap_counts(len(nb), n_boot, seed + 1)
    return value, scale * (_ratio(ca @ na, ca @ da) - _ratio(cb @ nb, cb @ db))


def bootstrap_ratio_gap(
    a: tuple[Sequence[float], Sequence[float], Sequence[Hashable]],
    b: tuple[Sequence[float], Sequence[float], Sequence[Hashable]],
    scale: float = 1.0,
    n_boot: int = N_BOOT,
    seed: int = 0,
    level: float = 0.95,
) -> Estimate:
    """Difference of two ratios on disjoint cluster sets; each set is resampled on its own."""
    value, draws = _gap_draws(a, b, scale, n_boot, seed)
    return _interval(value, draws, level)


def bootstrap_ratio_gap_test(
    a: tuple[Sequence[float], Sequence[float], Sequence[Hashable]],
    b: tuple[Sequence[float], Sequence[float], Sequence[Hashable]],
    scale: float = 1.0,
    n_boot: int = N_BOOT,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[Estimate, float]:
    """:func:`bootstrap_ratio_gap` plus its two-sided bootstrap p-value (same draws)."""
    value, draws = _gap_draws(a, b, scale, n_boot, seed)
    return _interval(value, draws, level), bootstrap_pvalue(draws)


def sign_flip_pvalue(d: Sequence[float], n_perm: int = N_PERM, seed: int = 0) -> float:
    """Two-sided sign-flip permutation p-value for ``sum(d) = 0`` (``d`` = per-game sums).

    Exact enumeration for up to ``EXACT_PERM_MAX_CLUSTERS`` games, Monte Carlo otherwise.
    """
    d = np.asarray(d, dtype=float)
    if len(d) == 0:
        return math.nan
    obs = abs(d.sum())
    tol = 1e-12 * max(1.0, float(np.abs(d).sum()))
    if len(d) <= EXACT_PERM_MAX_CLUSTERS:
        signs = np.array(list(product((1.0, -1.0), repeat=len(d))))
        stats = np.abs(signs @ d)
        return float(np.mean(stats >= obs - tol))
    rng = np.random.default_rng(seed)
    signs = rng.choice((1.0, -1.0), size=(n_perm, len(d)))
    stats = np.abs(signs @ d)
    return float((1 + np.sum(stats >= obs - tol)) / (n_perm + 1))


def paired_difference(
    num_a: Sequence[float],
    num_b: Sequence[float],
    den: Sequence[float],
    clusters: Sequence[Hashable],
    scale: float = 1.0,
    n_boot: int = N_BOOT,
    n_perm: int = N_PERM,
    seed: int = 0,
    level: float = 0.95,
) -> PairedResult:
    """``scale * (sum(a) - sum(b)) / sum(den)`` on shared episodes.

    Interval: game-clustered bootstrap. p-value: sign flips of per-game differences (the
    denominator is the same under the null, so only the numerator is permuted).
    """
    diff = np.asarray(num_a, dtype=float) - np.asarray(num_b, dtype=float)
    est = bootstrap_ratio(diff, den, clusters, scale, n_boot, seed, level)
    _, (d_g,) = cluster_sums(clusters, diff)
    p = sign_flip_pvalue(d_g, n_perm, seed)
    return PairedResult(est, p, len(diff), len(d_g))


def holm(p_values: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values (NaNs are passed through and not counted)."""
    p = np.asarray(p_values, dtype=float)
    out = np.full(len(p), math.nan)
    ok = np.flatnonzero(np.isfinite(p))
    m = len(ok)
    running = 0.0
    for rank, i in enumerate(ok[np.argsort(p[ok], kind="stable")]):
        running = max(running, min(1.0, (m - rank) * p[i]))
        out[i] = running
    return out.tolist()


def rank_probabilities(
    num: Mapping[str, Mapping[Hashable, float]],
    den: Mapping[str, Mapping[Hashable, float]],
    n_boot: int = N_BOOT,
    seed: int = 0,
) -> dict[str, list[float]]:
    """P(agent has rank k) for k = 1..n under a shared game bootstrap (rank 1 = highest ratio).

    ``num[agent][game]`` and ``den[agent][game]`` are per-game sums of each agent's score.
    """
    agents = list(num)
    games = sorted({g for a in agents for g in num[a]}, key=str)
    gi = {g: i for i, g in enumerate(games)}
    nm = np.zeros((len(agents), len(games)))
    dm = np.zeros((len(agents), len(games)))
    for ai, a in enumerate(agents):
        for g, v in num[a].items():
            nm[ai, gi[g]] = v
        for g, v in den[a].items():
            dm[ai, gi[g]] = v
    counts = bootstrap_counts(len(games), n_boot, seed)
    scores = _ratio(counts @ nm.T, counts @ dm.T)  # (n_boot, n_agents)
    scores = np.where(np.isfinite(scores), scores, -np.inf)
    order = np.argsort(-scores, axis=1, kind="stable")
    ranks = np.empty_like(order)
    rows = np.arange(n_boot)[:, None]
    ranks[rows, order] = np.arange(len(agents))[None, :]
    return {
        a: [float(np.mean(ranks[:, ai] == k)) for k in range(len(agents))]
        for ai, a in enumerate(agents)
    }


def clustered_se(x: Sequence[float], clusters: Sequence[Hashable]) -> float:
    """Cluster-robust standard error of the mean of ``x`` (clusters = games)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return math.nan
    _, (s_g, n_g) = cluster_sums(clusters, x, np.ones(n))
    g = len(s_g)
    if g < 2:
        return math.nan
    resid = s_g - n_g * x.mean()
    return float(math.sqrt(g / (g - 1) * np.sum(resid**2)) / n)


def episodes_needed(sd: float, delta: float, alpha: float = 0.05, power: float = 0.8) -> float:
    """Episodes needed for a two-sided z-test of a mean (or paired difference) of ``delta``."""
    if not (sd > 0 and delta > 0):
        return math.nan
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)
    return float(math.ceil((z * sd / delta) ** 2))


def variance_reduction(
    pnl: Sequence[float],
    xpnl: Sequence[float],
    clusters: Sequence[Hashable],
    delta: float = 0.1,
    alpha: float = 0.05,
    power: float = 0.8,
) -> dict[str, float]:
    """Compare realized P&L with expected P&L as the per-episode score.

    Both are unbiased for the same mean. Inputs are per-episode values in sd units (or paired
    differences of them). Episodes needed assume independent episodes at the per-episode SD.
    """
    pnl = np.asarray(pnl, dtype=float)
    xpnl = np.asarray(xpnl, dtype=float)
    sd_p = float(np.std(pnl, ddof=1)) if len(pnl) > 1 else math.nan
    sd_x = float(np.std(xpnl, ddof=1)) if len(xpnl) > 1 else math.nan
    se_p = clustered_se(pnl, clusters)
    se_x = clustered_se(xpnl, clusters)
    n_p = episodes_needed(sd_p, delta, alpha, power)
    n_x = episodes_needed(sd_x, delta, alpha, power)
    return {
        "n": len(pnl),
        "mean_pnl": float(pnl.mean()) if len(pnl) else math.nan,
        "mean_xpnl": float(xpnl.mean()) if len(xpnl) else math.nan,
        "sd_pnl": sd_p,
        "sd_xpnl": sd_x,
        "se_pnl": se_p,
        "se_xpnl": se_x,
        "se_ratio": se_p / se_x if se_x > 0 else math.nan,
        "delta": delta,
        "episodes_needed_pnl": n_p,
        "episodes_needed_xpnl": n_x,
        "episodes_ratio": (sd_p / sd_x) ** 2 if sd_x > 0 else math.nan,
    }
