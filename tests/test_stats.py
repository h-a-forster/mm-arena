"""Statistics: clustered bootstrap, paired tests, Holm, ranks, power."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mmarena.stats import (
    bootstrap_mean,
    bootstrap_ratio,
    bootstrap_ratio_gap,
    clustered_se,
    episodes_needed,
    holm,
    paired_difference,
    rank_probabilities,
    sign_flip_pvalue,
    variance_reduction,
)


def test_bootstrap_is_deterministic_and_covers_estimate():
    rng = np.random.default_rng(1)
    x = rng.normal(1.0, 1.0, 200)
    cl = np.repeat(np.arange(50), 4)
    a = bootstrap_mean(x, cl, seed=3)
    b = bootstrap_mean(x, cl, seed=3)
    assert a == b
    assert a.lo < a.value < a.hi
    assert a.value == pytest.approx(x.mean())


def test_bootstrap_ratio_constant_ratio_has_zero_width():
    den = np.arange(1, 21, dtype=float)
    est = bootstrap_ratio(2 * den, den, list(range(20)), scale=100.0)
    assert est.value == pytest.approx(200.0)
    assert est.lo == pytest.approx(200.0) and est.hi == pytest.approx(200.0)


def test_cluster_bootstrap_is_wider_than_naive_for_correlated_episodes():
    rng = np.random.default_rng(0)
    game_effect = np.repeat(rng.normal(0, 1, 30), 10)
    x = game_effect + rng.normal(0, 0.1, 300)
    clustered = bootstrap_mean(x, np.repeat(np.arange(30), 10))
    naive = bootstrap_mean(x, np.arange(300))
    assert (clustered.hi - clustered.lo) > 2 * (naive.hi - naive.lo)


def test_clustered_se_matches_classical_for_singletons():
    rng = np.random.default_rng(2)
    x = rng.normal(size=40)
    assert clustered_se(x, range(40)) == pytest.approx(x.std(ddof=1) / math.sqrt(40))


def test_sign_flip_exact_and_monte_carlo():
    # All four per-game differences positive: only the identity and its negation are as extreme.
    assert sign_flip_pvalue([1.0, 1.0, 1.0, 1.0]) == pytest.approx(2 / 16)
    assert sign_flip_pvalue([1.0, -1.0, 1.0, -1.0]) == pytest.approx(1.0)
    p = sign_flip_pvalue(np.full(40, 0.5), n_perm=2000, seed=0)
    assert p < 0.001
    assert sign_flip_pvalue(np.full(40, 0.5), n_perm=2000, seed=0) == p


def test_paired_difference():
    rng = np.random.default_rng(4)
    games = np.repeat(np.arange(30), 2)
    base = rng.normal(1.0, 1.0, 60)
    a, b = base + 0.3, base
    res = paired_difference(a, b, np.ones(60), games, scale=1.0)
    assert res.diff.value == pytest.approx(0.3)
    assert res.p_value < 0.01
    assert res.n_games == 30 and res.n_episodes == 60
    same = paired_difference(base, base, np.ones(60), games)
    assert same.diff.value == 0 and same.p_value == 1.0


def test_gap_resamples_strata_independently():
    est = bootstrap_ratio_gap(
        ([2.0] * 10, [1.0] * 10, list(range(10))),
        ([1.0] * 10, [1.0] * 10, list(range(10, 20))),
        scale=100.0,
    )
    assert est.value == pytest.approx(100.0)
    assert est.lo == pytest.approx(100.0)


def test_holm():
    adj = holm([0.01, 0.04, 0.03, 0.005])
    assert adj == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert math.isnan(holm([0.01, math.nan])[1])


def test_rank_probabilities():
    games = [f"g{i}" for i in range(20)]
    num = {
        "good": {g: 2.0 for g in games},
        "mid": {g: 1.0 for g in games},
        "bad": {g: -1.0 for g in games},
    }
    den = {k: {g: 1.0 for g in games} for k in num}
    probs = rank_probabilities(num, den, n_boot=200)
    assert probs["good"] == [1.0, 0.0, 0.0]
    assert probs["bad"] == [0.0, 0.0, 1.0]
    for p in probs.values():
        assert sum(p) == pytest.approx(1.0)


def test_episodes_needed_and_variance_reduction():
    # (1.96 + 0.84)^2 = 7.85 -> 8 episodes for sd = delta.
    assert episodes_needed(1.0, 1.0) == 8
    rng = np.random.default_rng(5)
    x = rng.normal(0.5, 0.5, 400)
    p = x + rng.normal(0, 1.5, 400)
    vr = variance_reduction(p, x, np.arange(400), delta=0.1)
    assert vr["se_ratio"] > 2
    assert vr["episodes_ratio"] == pytest.approx((vr["sd_pnl"] / vr["sd_xpnl"]) ** 2)
    assert vr["episodes_needed_pnl"] > vr["episodes_needed_xpnl"]


def test_bootstrap_pvalue_and_gap_test():
    from mmarena.stats import bootstrap_pvalue, bootstrap_ratio_gap_test

    assert bootstrap_pvalue([1.0, 2.0, 3.0]) == pytest.approx(0.0)
    assert bootstrap_pvalue([-1.0, 1.0]) == pytest.approx(1.0)
    assert bootstrap_pvalue([0.0, 0.0, 1.0, 2.0]) == pytest.approx(1.0)
    assert math.isnan(bootstrap_pvalue([math.nan]))
    rng = np.random.default_rng(3)
    a = (rng.normal(5, 1, 30), np.ones(30), list(range(30)))
    b = (rng.normal(0, 1, 30), np.ones(30), list(range(30, 60)))
    est, p = bootstrap_ratio_gap_test(a, b, 1.0, 500, 1)
    assert est == bootstrap_ratio_gap(a, b, 1.0, 500, 1)
    assert p < 0.01 and est.lo > 0
